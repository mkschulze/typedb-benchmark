"""Independent SQLite rule execution over public JSON facts, equivalent to TypeQL functions."""

import json
import sqlite3

# Every condition and calculation below is executed by SQLite, not precomputed in Python.
QUERY = """
WITH input AS (
 SELECT json_extract(body,'$.gross_amount_cents') AS gross,
 json_extract(body,'$.payment_date') AS payment,
 json_extract(body,'$.knowledge_date') AS knowledge,
 json_extract(body,'$.payer.id') AS payer_id,
 json_extract(body,'$.recipient.id') AS recipient_id,
 json_extract(body,'$.payer.country') AS payer_country,
 json_extract(body,'$.payer.legal_form') AS payer_form,
 json_extract(body,'$.recipient.country') AS recipient_country,
 json_extract(body,'$.facts') AS f,
 json_extract(body,'$.documents') AS docs
 FROM fixture
), conditions AS (
 SELECT *, json_extract(f,'$.requested_route') AS route,
 EXISTS (SELECT 1 FROM json_each(docs) d
 WHERE json_extract(d.value,'$.kind')='bzst_exemption'
 AND json_extract(d.value,'$.route')=json_extract(f,'$.requested_route')
 AND (json_extract(f,'$.requested_route')!='treaty' OR json_extract(f,'$.direct_holding_basis_points')>=1000)
 AND json_extract(d.value,'$.payer_id')=payer_id
 AND json_extract(d.value,'$.recipient_id')=recipient_id
 AND json_extract(d.value,'$.issued_at')<=payment
 AND json_extract(d.value,'$.available_at')<=payment
 AND json_extract(d.value,'$.issued_at')<=knowledge
 AND json_extract(d.value,'$.valid_from')<=payment
 AND json_extract(d.value,'$.valid_until')>=payment
 AND json_extract(d.value,'$.revoked')=0) AS valid_certificate,
 (json_extract(f,'$.listed_exception')=1 OR json_extract(f,'$.main_purpose_exception')=1
  OR json_extract(f,'$.owners_entitled')=1 OR json_extract(f,'$.economic_link')=1) AS abuse_clear,
 (json_extract(f,'$.listed_exception')=0 AND json_extract(f,'$.main_purpose_exception')=0
  AND json_extract(f,'$.owners_entitled')=0 AND json_extract(f,'$.economic_link')=0) AS abuse_denied,
 CASE WHEN json_extract(f,'$.direct_holding_basis_points')>=1000
 AND date(json_extract(f,'$.ownership_since'),'+364 days')<=payment THEN 5 ELSE 15 END AS treaty_percent,
 date(json_extract(f,'$.ownership_since'),'+1 year') AS holding_anniversary,
 (SELECT json_group_array(key) FROM json_each(f)
  WHERE value IS NULL AND (key IN ('payer_unlimited_taxable','recipient_eu_resident')
   OR (json_extract(f,'$.requested_route')='section43b' AND key IN ('recipient_qualifying_form','recipient_subject_to_tax','direct_holding_basis_points','resolution_holding_basis_points','ownership_since','ownership_continuous'))
   OR (json_extract(f,'$.requested_route')='treaty' AND key IN ('beneficial_owner','direct_holding_basis_points','ownership_since')))) AS missing
 FROM input
), decision AS (
 SELECT *, CASE
 WHEN payer_country!='DE' OR payer_form!='GmbH' OR recipient_country!='NL'
 OR json_extract(f,'$.recipient_kind')!='corporation' OR json_extract(f,'$.distribution_kind')!='ordinary_cash_dividend'
 OR json_extract(f,'$.permanent_establishment_attribution')!=0 OR payment<'2026-01-01' OR payment>'2026-11-21' THEN 8
 WHEN knowledge<payment THEN 10
 WHEN gross<0 OR gross%4!=0 OR json_extract(f,'$.ownership_continuous')=0 THEN 11
 WHEN route='domestic_withholding' THEN 0
 WHEN route='comprehensive_relief' OR json_extract(f,'$.records_conflict')=1 OR json_extract(f,'$.ao42_concern')!=0 THEN 7
 WHEN json_array_length(missing)>0 THEN 6
 WHEN json_extract(f,'$.payer_unlimited_taxable')=0 OR json_extract(f,'$.recipient_eu_resident')=0 THEN 3
 WHEN route='section43b' AND (json_extract(f,'$.recipient_qualifying_form')=0 OR json_extract(f,'$.recipient_subject_to_tax')=0
 OR (json_extract(f,'$.direct_holding_basis_points')<1000 AND json_extract(f,'$.resolution_holding_basis_points')<1000)) THEN 3
 WHEN route='treaty' AND json_extract(f,'$.beneficial_owner')=0 THEN 3
 WHEN abuse_denied=1 THEN 3
 WHEN COALESCE(abuse_clear,0)=0 OR json_extract(f,'$.ao42_concern') IS NULL THEN 7
 WHEN route='section43b' AND holding_anniversary>knowledge THEN 4
 WHEN json_extract(f,'$.certificate_inventory_complete') IS NOT 1 AND valid_certificate=0 THEN 9
 WHEN route='section43b' AND holding_anniversary>payment THEN 5
 WHEN valid_certificate=1 THEN 2 ELSE 1 END AS decision_code,
 gross/4 AS domestic_tax,
 (gross/4)*55/1000 AS domestic_surcharge,
 CASE WHEN route='treaty' THEN gross*treaty_percent/100 ELSE 0 END AS relief_cap
 FROM conditions
), money AS (
 SELECT *, CASE WHEN decision_code IN (8,9,10,11) THEN NULL
 WHEN decision_code=2 THEN relief_cap ELSE domestic_tax END AS tax_cents,
 CASE WHEN decision_code IN (8,9,10,11) THEN NULL
 WHEN decision_code=2 THEN 0 ELSE domestic_surcharge END AS surcharge_cents,
 CASE WHEN decision_code IN (1,5) THEN domestic_tax+domestic_surcharge-relief_cap
 WHEN decision_code IN (2,3) THEN 0 ELSE NULL END AS refund_cents
 FROM decision
)
SELECT decision_code,tax_cents,surcharge_cents,tax_cents+surcharge_cents AS total_cents,
 gross-tax_cents-surcharge_cents AS net_cents,refund_cents,
 CASE WHEN decision_code=9 THEN '["certificate_inventory_complete"]'
 WHEN decision_code=10 THEN '["payment_time_facts"]' ELSE missing END AS missing_facts
FROM money
"""


def evaluate_sql(case: dict) -> dict:
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE fixture(body TEXT NOT NULL)")
        db.execute("INSERT INTO fixture VALUES (?)", (json.dumps(case),))
        result = dict(db.execute(QUERY).fetchone())
    result["missing_facts"] = sorted(json.loads(result["missing_facts"]))
    return result
