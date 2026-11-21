"""Rebuild explicit synthetic fixtures. Gold amounts below are separately authored, not engine output."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).parent
BASE_SOURCES = [
    "estg-43a",
    "estg-44",
    "estg-50c",
    "solzg-3",
    "solzg-4",
    "bzst-refund",
    "implementation-rules",
]
EU_SOURCES = BASE_SOURCES + ["estg-43b", "estg-annex2", "estg-50d3", "bzst-exemption"]
TREATY_SOURCES = BASE_SOURCES + ["dba-nl-2026", "dba-nl-register", "solzg-5", "estg-50d3"]
DEFAULT = dict(
    requested_route="section43b",
    distribution_kind="ordinary_cash_dividend",
    recipient_kind="corporation",
    payer_unlimited_taxable=True,
    recipient_eu_resident=True,
    recipient_qualifying_form=True,
    recipient_subject_to_tax=True,
    beneficial_owner=True,
    permanent_establishment_attribution=False,
    direct_holding_basis_points=2500,
    resolution_holding_basis_points=2500,
    ownership_since="2024-01-01",
    ownership_continuous=True,
    owners_entitled=None,
    economic_link=None,
    listed_exception=True,
    main_purpose_exception=False,
    ao42_concern=False,
    certificate_inventory_complete=True,
    records_conflict=False,
)
CASES = []
GOLD = {}


def add(
    n,
    title,
    category,
    group,
    gross=10_000_000,
    changes=None,
    certificate=None,
    payment="2026-06-30",
    knowledge="2026-06-30",
    country="NL",
    extra_docs=None,
    expected=None,
    tax=None,
    soli=None,
    refund=None,
    status="determined",
    eligibility="eligible",
    refund_status="potential_on_application",
    missing=None,
):
    split = "development" if n.startswith("dev") else "evaluation"
    facts = deepcopy(DEFAULT)
    facts.update(changes or {})
    ids = (
        EU_SOURCES
        if facts["requested_route"] == "section43b"
        else TREATY_SOURCES
        if facts["requested_route"] == "treaty"
        else BASE_SOURCES
    )
    if facts["requested_route"] == "comprehensive_relief":
        ids = list(dict.fromkeys(EU_SOURCES + TREATY_SOURCES + ["estg-44a9", "kstg-32"]))
    docs = [
        dict(
            id=f"{n}-payment",
            title="Synthetic payment and company record",
            recorded_at=knowledge,
            text=f"Synthetic case: German GmbH pays {facts['distribution_kind']} of {gross} euro cents on {payment}. Recipient is a {country} {facts['recipient_kind']}; German permanent establishment attribution: {facts['permanent_establishment_attribution']}. Company form, residence, tax status and all qualification values are explicitly specified in facts.",
            kind="company_record",
        ),
        dict(
            id=f"{n}-ownership",
            title="Dated synthetic ownership evidence",
            recorded_at=knowledge,
            text=f"At payment direct participation is {facts['direct_holding_basis_points']} basis points; at the distribution resolution it is {facts['resolution_holding_basis_points']} basis points. Current uninterrupted qualifying holding began {facts['ownership_since']}; continuous: {facts['ownership_continuous']}. Use the dated current record over superseded notes.",
            kind="ownership_record",
        ),
        dict(
            id=f"{n}-abuse",
            title="Synthetic statutory exception facts",
            recorded_at=knowledge,
            text=f"Main class of shares significantly and regularly traded on recognized exchange: {facts['listed_exception']}. Proof that no main purpose was tax advantage: {facts['main_purpose_exception']}. Direct owners would be entitled: {facts['owners_entitled']}; material economic link: {facts['economic_link']}. Separate AO §42 concern: {facts['ao42_concern']}. Unknown evidence does not prove abuse.",
            kind="anti_abuse_record",
        ),
        dict(
            id=f"{n}-inventory",
            title="Certificate inventory statement",
            recorded_at=knowledge,
            text=f"Inventory complete for this recipient and payer at payment: {facts['certificate_inventory_complete']}. Documents not listed are absent only when completeness is true. A residence document or application is not an issued BZSt exemption.",
            kind="inventory",
        ),
    ]
    if certificate:
        cert = dict(
            id=f"{n}-certificate",
            title="Synthetic BZSt exemption certificate",
            kind="bzst_exemption",
            route="section43b" if facts["requested_route"] == "section43b" else "treaty",
            issued_at="2026-01-15",
            available_at="2026-01-15",
            valid_from="2026-01-01",
            valid_until="2026-12-31",
            payer_id=f"{n}-payer",
            recipient_id=f"{n}-recipient",
            revoked=False,
        )
        cert.update(certificate)
        cert["text"] = (
            f"Synthetic document only. BZSt exemption; route {cert['route']}; issued {cert['issued_at']}; available {cert['available_at']}; valid {cert['valid_from']} through {cert['valid_until']} inclusive; payer {cert['payer_id']}; recipient {cert['recipient_id']}; revoked {cert['revoked']}."
        )
        docs.append(cert)
    docs.extend(extra_docs or [])
    route = facts["requested_route"]
    limitation = {
        "section43b": "Assess only the §43b route and withholding at payment. Refund figures are the potential relief under that route, assuming tax was remitted, a timely valid application and required tax certificate; do not decide other treaty/§44a(9)/KStG §32 routes.",
        "treaty": "Assess only ordinary Netherlands treaty Article 10 relief and withholding at payment under the 2026 consolidated treaty. Refund figures are conditional on a timely valid application, remittance and tax certificate. Do not decide §43b or other domestic refund routes.",
        "domestic_withholding": "Calculate domestic withholding at payment only; no exemption certificate exists. Do not assess substantive relief or refunds.",
        "comprehensive_relief": "Assess all possible dividend relief routes; do not assume a named route exhausts §44a(9), KStG §32 or treaty relief.",
    }[route]
    CASES.append(
        dict(
            id=n,
            title=title,
            summary=title + ". " + limitation,
            category=category,
            split=split,
            template_group=group,
            question=f"What must the payer withhold on {payment}, and what is the status of relief as known on {knowledge}? "
            + limitation,
            gross_amount_cents=gross,
            payment_date=payment,
            knowledge_date=knowledge,
            payer=dict(id=f"{n}-payer", name="Rhein Components GmbH", country="DE", legal_form="GmbH"),
            recipient=dict(id=f"{n}-recipient", name="Delta Industries BV", country=country, legal_form="BV"),
            facts=facts,
            documents=docs,
            source_ids=ids,
            review_status="provisional",
        )
    )
    ex = dict(
        status=status,
        relief_eligibility=eligibility,
        withholding_tax_cents=tax,
        solidarity_surcharge_cents=soli,
        total_withholding_cents=None if tax is None or soli is None else tax + soli,
        net_payment_cents=None if tax is None or soli is None else gross - tax - soli,
        refund_amount_cents=refund,
        refund_status=refund_status,
        missing_facts=missing or [],
    )
    ex.update(expected or {})
    required_sources = {
        "domestic_withholding": ["estg-43a", "estg-44", "solzg-4"],
        "section43b": ["estg-43b", "estg-50c", "estg-50d3"],
        "treaty": ["dba-nl-2026", "estg-50c", "solzg-5"],
        "comprehensive_relief": ["estg-44a9", "kstg-32"],
    }[route]
    required_evidence = [f"{n}-payment", f"{n}-inventory"]
    if route in ("section43b", "treaty"):
        required_evidence.extend([f"{n}-ownership", f"{n}-abuse"])
    if certificate:
        required_evidence.append(f"{n}-certificate")
    GOLD[n] = dict(
        expected=ex,
        required_source_ids=required_sources,
        required_evidence_ids=required_evidence,
        review_status="provisional",
        authorship="Manually specified scenario rubric and arithmetic; not derived from reference, SQL or TypeDB outputs. Independent legal approval pending.",
    )


# Development templates are deliberately excluded from evaluation.
add(
    "dev-01",
    "Eligible parent; no exemption certificate",
    "certificates",
    "dev-plain-absent",
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "dev-02",
    "Eligible parent; issued exemption certificate",
    "certificates",
    "dev-plain-issued",
    certificate={"route": "section43b"},
    tax=0,
    soli=0,
    refund=0,
    refund_status="not_needed",
)
add(
    "dev-03",
    "Explicit restriction; both statutory prongs proved",
    "missing_review",
    "dev-proven-restriction",
    gross=200_000,
    changes={
        "listed_exception": False,
        "main_purpose_exception": False,
        "owners_entitled": False,
        "economic_link": False,
    },
    tax=50_000,
    soli=2750,
    refund=0,
    eligibility="ineligible",
    refund_status="unavailable_under_requested_route",
)
add(
    "dev-04",
    "Five percent parent; §43b route only",
    "eu_eligibility",
    "dev-five-percent",
    changes={"direct_holding_basis_points": 500, "resolution_holding_basis_points": 500},
    tax=2_500_000,
    soli=137_500,
    refund=0,
    eligibility="ineligible",
    refund_status="unavailable_under_requested_route",
)
add(
    "dev-05",
    "Holding period will finish after payment",
    "eu_eligibility",
    "dev-holding-forward",
    changes={"ownership_since": "2026-02-01"},
    tax=2_500_000,
    soli=137_500,
    refund=None,
    eligibility="undetermined",
    refund_status="conditional_on_holding_completion",
)
add(
    "dev-06",
    "Residence evidence is not BZSt exemption",
    "certificates",
    "dev-residence-only",
    extra_docs=[
        dict(
            id="dev-06-residence",
            title="Dutch residence document",
            kind="residence",
            text="Tax residence in the Netherlands confirmed. This is not a German BZSt exemption certificate.",
            issued_at="2026-01-01",
        )
    ],
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "dev-07",
    "Treaty five percent certificate",
    "treaty_relief",
    "dev-treaty-issued",
    changes={"requested_route": "treaty"},
    certificate={"route": "treaty"},
    tax=500_000,
    soli=0,
    refund=0,
    refund_status="not_needed",
)
add(
    "dev-08",
    "Treaty claimant is not the beneficial owner",
    "treaty_relief",
    "dev-treaty-owner-denial",
    changes={
        "requested_route": "treaty",
        "beneficial_owner": False,
        "ownership_since": "2026-04-01",
    },
    tax=2_500_000,
    soli=137_500,
    refund=0,
    eligibility="ineligible",
    refund_status="unavailable_under_requested_route",
)
add(
    "dev-09",
    "Unresolved substance facts",
    "missing_review",
    "dev-unresolved-abuse",
    changes={"listed_exception": None, "main_purpose_exception": None},
    tax=2_500_000,
    soli=137_500,
    refund=None,
    status="review_required",
    eligibility="undetermined",
    refund_status="requires_review",
)
add(
    "dev-10",
    "Individual recipient outside scope",
    "missing_review",
    "dev-individual",
    changes={"recipient_kind": "individual"},
    status="outside_scope",
    eligibility="undetermined",
    refund_status="not_assessed",
)

# Five held-out cases per family, with explicit independent expected amounts.
add(
    "eval-01",
    "Domestic withholding on €48,000",
    "base_math",
    "eval-domestic-manufacturing",
    gross=4_800_000,
    changes={"requested_route": "domestic_withholding"},
    tax=1_200_000,
    soli=66_000,
    eligibility="undetermined",
    refund_status="not_assessed",
)
add(
    "eval-02",
    "Surcharge fractional cent is discarded",
    "base_math",
    "eval-domestic-cent-rounding",
    gross=100_004,
    changes={"requested_route": "domestic_withholding"},
    tax=25_001,
    soli=1375,
    eligibility="undetermined",
    refund_status="not_assessed",
)
add(
    "eval-03",
    "Zero cash distribution",
    "base_math",
    "eval-domestic-zero",
    gross=0,
    changes={"requested_route": "domestic_withholding"},
    tax=0,
    soli=0,
    eligibility="undetermined",
    refund_status="not_assessed",
)
add(
    "eval-04",
    "Large exact cash dividend",
    "base_math",
    "eval-domestic-large",
    gross=123_456_780,
    changes={"requested_route": "domestic_withholding"},
    tax=30_864_195,
    soli=1_697_530,
    eligibility="undetermined",
    refund_status="not_assessed",
)
add(
    "eval-05",
    "Small dividend; withholding versus remittance",
    "base_math",
    "eval-domestic-small",
    gross=404,
    changes={"requested_route": "domestic_withholding"},
    tax=101,
    soli=5,
    eligibility="undetermined",
    refund_status="not_assessed",
)
add(
    "eval-06",
    "Ten percent statutory boundary",
    "eu_eligibility",
    "eval-eu-threshold",
    changes={"direct_holding_basis_points": 1000, "resolution_holding_basis_points": 1000},
    gross=4_000_000,
    tax=1_000_000,
    soli=55_000,
    refund=1_055_000,
)
add(
    "eval-07",
    "9.99 percent at both relevant dates",
    "eu_eligibility",
    "eval-eu-below-boundary",
    changes={"direct_holding_basis_points": 999, "resolution_holding_basis_points": 999},
    tax=2_500_000,
    soli=137_500,
    refund=0,
    eligibility="ineligible",
    refund_status="unavailable_under_requested_route",
)
add(
    "eval-08",
    "Corporate recipient exempt from Dutch profit tax",
    "eu_eligibility",
    "eval-eu-tax-exempt",
    changes={"recipient_subject_to_tax": False},
    tax=2_500_000,
    soli=137_500,
    refund=0,
    eligibility="ineligible",
    refund_status="unavailable_under_requested_route",
)
add(
    "eval-09",
    "Twelve months completed after payment; now evidenced",
    "eu_eligibility",
    "eval-eu-later-completion",
    changes={"ownership_since": "2025-08-01"},
    knowledge="2026-09-01",
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "eval-10",
    "Interrupted holding resets the qualifying start",
    "eu_eligibility",
    "eval-eu-interruption",
    changes={"ownership_since": "2026-04-01"},
    tax=2_500_000,
    soli=137_500,
    refund=None,
    eligibility="undetermined",
    refund_status="conditional_on_holding_completion",
    extra_docs=[
        dict(
            id="eval-10-interruption",
            title="Earlier holding ended",
            kind="ownership_record",
            text="Earlier holding ended 2026-03-01. A new uninterrupted holding began 2026-04-01. Do not aggregate separated periods.",
        )
    ],
)
add(
    "eval-11",
    "Certificate expires on the payment day",
    "certificates",
    "eval-cert-inclusive-end",
    certificate={"valid_until": "2026-06-30"},
    tax=0,
    soli=0,
    refund=0,
    refund_status="not_needed",
)
add(
    "eval-12",
    "Certificate expired one day before payment",
    "certificates",
    "eval-cert-expired",
    certificate={"valid_until": "2026-06-29"},
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "eval-13",
    "Certificate issued after payment",
    "certificates",
    "eval-cert-retroactive",
    certificate={"issued_at": "2026-07-01", "available_at": "2026-07-01"},
    knowledge="2026-07-15",
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "eval-14",
    "Certificate names another payer",
    "certificates",
    "eval-cert-wrong-payer",
    certificate={"payer_id": "other-gmbh"},
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "eval-15",
    "Application pending at payment",
    "certificates",
    "eval-cert-application",
    extra_docs=[
        dict(
            id="eval-15-application",
            title="BZSt application receipt",
            kind="application",
            text="Application received on 2026-06-01; no decision has been issued. Complete inventory confirms no BZSt exemption at payment.",
            issued_at="2026-06-01",
        )
    ],
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "eval-16",
    "Treaty 365-day inclusive boundary; surcharge reduced first",
    "treaty_relief",
    "eval-treaty-365-boundary",
    gross=6_000_000,
    changes={
        "requested_route": "treaty",
        "ownership_since": "2025-07-01",
        "direct_holding_basis_points": 1000,
        "resolution_holding_basis_points": 1000,
    },
    certificate={"route": "treaty"},
    tax=300_000,
    soli=0,
    refund=0,
    refund_status="not_needed",
)
add(
    "eval-17",
    "Treaty fifteen percent; nine percent portfolio",
    "treaty_relief",
    "eval-treaty-fifteen",
    gross=2_000_000,
    changes={
        "requested_route": "treaty",
        "direct_holding_basis_points": 900,
        "resolution_holding_basis_points": 900,
    },
    tax=500_000,
    soli=27_500,
    refund=227_500,
)
add(
    "eval-18",
    "Treaty purpose exception without payment exemption",
    "treaty_relief",
    "eval-treaty-proven-purpose-exception",
    gross=8_000_000,
    changes={
        "requested_route": "treaty",
        "listed_exception": False,
        "main_purpose_exception": True,
        "owners_entitled": False,
        "economic_link": False,
    },
    tax=2_000_000,
    soli=110_000,
    refund=1_710_000,
)
add(
    "eval-19",
    "Treaty beneficial ownership unconfirmed",
    "treaty_relief",
    "eval-treaty-owner-unknown",
    changes={"requested_route": "treaty", "beneficial_owner": None},
    tax=2_500_000,
    soli=137_500,
    status="needs_information",
    eligibility="undetermined",
    refund_status="undetermined",
    missing=["beneficial_owner"],
)
add(
    "eval-20",
    "Request for exhaustive best relief route",
    "treaty_relief",
    "eval-comprehensive-routes",
    changes={
        "requested_route": "comprehensive_relief",
        "direct_holding_basis_points": 500,
        "resolution_holding_basis_points": 500,
    },
    tax=2_500_000,
    soli=137_500,
    status="review_required",
    eligibility="undetermined",
    refund_status="requires_review",
)
add(
    "eval-21",
    "Current ownership supersedes old cap table",
    "dates_stale",
    "eval-ownership-superseded",
    changes={"direct_holding_basis_points": 500, "resolution_holding_basis_points": 500},
    extra_docs=[
        dict(
            id="eval-21-stale",
            title="Superseded 2024 ownership note",
            kind="stale_record",
            recorded_at="2024-01-01",
            text="Old cap table showed 25%. Superseded by dated current ownership record showing 5% at resolution and payment.",
        )
    ],
    tax=2_500_000,
    soli=137_500,
    refund=0,
    eligibility="ineligible",
    refund_status="unavailable_under_requested_route",
)
add(
    "eval-22",
    "Information cutoff predates payment",
    "dates_stale",
    "eval-cutoff-before-payment",
    knowledge="2026-06-01",
    status="needs_information",
    eligibility="undetermined",
    refund_status="undetermined",
    missing=["payment_time_facts"],
)
add(
    "eval-23",
    "Holding completion lies beyond knowledge cutoff",
    "dates_stale",
    "eval-cutoff-holding",
    changes={"ownership_since": "2025-10-01"},
    knowledge="2026-09-01",
    tax=2_500_000,
    soli=137_500,
    refund=None,
    eligibility="undetermined",
    refund_status="conditional_on_holding_completion",
)
add(
    "eval-24",
    "Certificate not available to payer until July",
    "dates_stale",
    "eval-document-delivery",
    certificate={"available_at": "2026-07-03"},
    knowledge="2026-07-10",
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "eval-25",
    "Certificate revoked before payment",
    "dates_stale",
    "eval-document-revocation",
    certificate={"revoked": True},
    tax=2_500_000,
    soli=137_500,
    refund=2_637_500,
)
add(
    "eval-26",
    "Certificate inventory is explicitly unknown",
    "missing_review",
    "eval-missing-inventory",
    changes={"certificate_inventory_complete": None},
    status="needs_information",
    eligibility="eligible",
    refund_status="undetermined",
    missing=["certificate_inventory_complete"],
)
add(
    "eval-27",
    "Qualifying legal form not established",
    "missing_review",
    "eval-missing-form",
    changes={"recipient_qualifying_form": None},
    tax=2_500_000,
    soli=137_500,
    status="needs_information",
    eligibility="undetermined",
    refund_status="undetermined",
    missing=["recipient_qualifying_form"],
)
add(
    "eval-28",
    "Anti-abuse conditions require legal review",
    "missing_review",
    "eval-review-abuse",
    changes={
        "listed_exception": False,
        "main_purpose_exception": None,
        "economic_link": None,
        "owners_entitled": False,
    },
    tax=2_500_000,
    soli=137_500,
    status="review_required",
    eligibility="undetermined",
    refund_status="requires_review",
)
add(
    "eval-29",
    "Swiss recipient outside first jurisdiction",
    "missing_review",
    "eval-outside-jurisdiction",
    country="CH",
    status="outside_scope",
    eligibility="undetermined",
    refund_status="not_assessed",
)
add(
    "eval-30",
    "Investment fund outside ordinary corporate scope",
    "missing_review",
    "eval-outside-fund",
    changes={"recipient_kind": "fund"},
    status="outside_scope",
    eligibility="undetermined",
    refund_status="not_assessed",
)

SUMMARIES = {
    "estg-43a": (
        "EStG §43a — domestic rate",
        "§43a(1) no.1 and (2)",
        "Summary: Ordinary corporate dividends fall under the 25 percent capital income withholding rate on gross income. These fixtures avoid fractional-cent capital tax bases. This is payer withholding, not final tax burden.",
    ),
    "estg-44": (
        "EStG §44 — accrual and payer",
        "§44(1), especially sentences 2, 3 and 6",
        "Summary: Capital income tax arises at receipt and the dividend debtor withholds for the recipient. The whole-euro rounding in sentence 6 concerns tax to be remitted together, not an instruction to round each recipient withholding down to whole euros. This benchmark reports withholding per payment, not the aggregated remittance return.",
    ),
    "estg-43b": (
        "EStG §43b — EU parent company route",
        "§43b(1), (2)",
        "Summary: On application qualifying EU parent-company dividends can be exempt, subject to §50d(3). A direct 10 percent participation is required; where not met at tax accrual, the distribution-resolution time is relevant. Twelve uninterrupted months are required. If completed after accrual, refund under §50c(3) applies and exemption at payment under §50c(2) is excluded. Liquidation and conversion distributions are excluded.",
    ),
    "estg-annex2": (
        "EStG Annex 2 — qualifying companies",
        "Annex 2 nos.1(t), 2, 3 and German GmbH entry 1(f)",
        "Summary: Annex 2 lists Dutch naamloze vennootschap and besloten vennootschap met beperkte aansprakelijkheid and German GmbH forms, requires EU tax residence without treaty third-state residence, and liability without option or exemption to listed company taxes including Dutch vennootschapsbelasting. Fixtures explicitly state those qualifications; the mere label BV is insufficient proof.",
    ),
    "estg-50c": (
        "EStG §50c — certificate and refund",
        "§50c(1), (2) no.1, (3)",
        "Summary: Relief eligibility under §43b or a treaty does not itself remove withholding. A BZSt exemption certificate can remove/reduce withholding within its scope and validity; an application or residence document is not that certificate. Certificates can cover at most five years and not before application receipt. A later issued certificate may support correction under statutory conditions, but does not mean the payer possessed it at payment. Refund requires timely application, remitted tax and required tax certificate; these are conditional, never automatic.",
    ),
    "estg-50d3": (
        "EStG §50d(3) — restrictions and exceptions",
        "§50d(3)",
        "Summary: Restriction depends on both unentitled underlying persons and lack of material connection between the income source and economic activity. The provision has proof-of-no-main-tax-purpose and main-share-class significant regular recognized-exchange trading exceptions; AO §42 remains. Missing substance proof alone does not establish denial. Unresolved legal judgments require review.",
    ),
    "estg-44a9": (
        "EStG §44a(9) — additional corporate refund",
        "§44a(9)",
        "Summary: A nonresident corporation within KStG §2 no.1 may obtain refund of two fifths of withheld and remitted capital income tax; §50c(3),(5) and §50d(3) apply correspondingly. Further §43b and treaty rights remain. A failed §43b claim does not prove absence of every domestic refund.",
    ),
    "kstg-32": (
        "KStG §32 — finality and refund rules",
        "§32, especially (5) and (6)",
        "Summary: KStG §32 contains additional rules on capital withholding finality and refund for qualifying corporate recipients with detailed conditions. The implementation does not automate a comprehensive claim under this section; exhaustive refund questions require legal review rather than asserting that a treaty or §43b result is final.",
    ),
    "solzg-3": (
        "SolzG §3 — surcharge base",
        "§3(1) no.5",
        "Summary: For tax withheld on capital income, the surcharge is based on the capital income tax to be withheld. Individual income-tax annual exemption thresholds do not create a corporate dividend-withholding exemption.",
    ),
    "solzg-4": (
        "SolzG §4 — surcharge rate and rounding",
        "§4",
        "Summary: The surcharge rate is 5.5 percent of the relevant tax base. Fractions of a cent are disregarded. Calculate surcharge from the capital income tax, not directly as a rounded 1.375 percent of gross.",
    ),
    "solzg-5": (
        "SolzG §5 — treaty reduction order",
        "§5",
        "Summary: When income tax raised under this statute is reduced by a tax treaty, apply the reduction first against the solidarity surcharge. A 5 or 15 percent combined treaty cap is not increased by adding 5.5 percent on top; these ordinary dividend caps are below the domestic 25 percent base tax, leaving zero surcharge after treaty relief.",
    ),
    "bzst-exemption": (
        "BZSt — exemption certificate guidance",
        "Exemption from capital-income withholding",
        "Summary: BZSt guidance distinguishes applications, issued exemption certificates, future reductions and possible corrections after retroactive issuance. Certificates may be for one to five years and can begin no earlier than the application date. Domestic filing obligations continue even at zero withholding.",
    ),
    "bzst-refund": (
        "BZSt — capital income tax refund guidance",
        "Refund service description",
        "Summary: BZSt describes ordinary German dividend withholding as 25 percent plus 5.5 percent surcharge and identifies conditional treaty and statutory relief/refund routes. This procedural summary does not itself establish eligibility.",
    ),
    "dba-nl-register": (
        "BMF — Netherlands treaty version register",
        "Protocol 14 April 2025 and consolidated text 2026",
        "Summary: The official BMF register records the 14 April 2025 protocol entering into force on 31 December 2025 and applying from 1 January 2026. The consolidated text announced 11 May 2026 incorporates that protocol; the original 2012 text alone is not the 2026 version.",
    ),
    "dba-nl-2026": (
        "Germany–Netherlands treaty, consolidated 2026",
        "BGBl. 2026 II no.102; Articles 2(3), 10(2),(4), 26",
        "Summary: For a Netherlands-resident beneficial owner, Article 10(2)(a) caps ordinary dividend tax at 5 percent for a company with at least 10 percent direct capital ownership over a 365-day period including payment; other ordinary corporate cases use 15 percent under (c). Restructuring continuity, funds, pension funds, REITs, German permanent establishment attribution and unresolved anti-abuse are not automated here. Article 2 includes income-tax surcharges. The 365-day condition is not the same as §43b’s twelve calendar months.",
    ),
}
records = json.loads((HERE / "raw/retrieval.json").read_text())
sources = []
for r in records:
    if "error" in r:
        raise RuntimeError(r)
    title, locator, summary = SUMMARIES[r["id"]]
    sources.append(
        dict(
            r,
            title=title,
            locator=locator,
            text=summary,
            review_status="provisional",
            application_date="2026-01-01" if r["id"].startswith("dba-nl") else None,
            version_note="Retrieved current official text; application to 2026 fixtures provisional pending independent legal review. No inferred historical version changes.",
        )
    )
rules = """Implementation scope and executable rules (provisional, not legal advice): ordinary cash dividend, German GmbH payer, Dutch corporation recipient, no PE attribution, 2026 payments at/before 21 November. Store unknown separately from false. Monetary inputs are integer euro cents; corpus capital taxes are exact to cents (gross divisible by four); surcharge is floor(capital tax cents *55/1000). Other fractional-cent capital-tax bases require review. Withholding differs from whole-euro aggregation/remittance. §43b: qualifying form/residence/company-tax status, direct holding>=10% at payment or resolution, uninterrupted twelve calendar months, explicit §50d(3) exception or facts negating at least one cumulative restriction limb, no unresolved AO42. Later holding completion permits conditional application-based refund; it never creates a payment-time exemption. An exemption needs issued/available at payment, current validity, correct payer/recipient/route, not revoked; empty list means absent only with explicit complete inventory. Treaty: use consolidated 2026 text, resident beneficial corporate owner; >=10% direct for at least365 days by payment permits5%, otherwise15%; a short period that could later complete stays15% at payment and no forward 5% refund is automated. Valid treaty exemption requires >=10% direct under §50c(2) and covers its route. Reduce surcharge first: treaty total cap has zero surcharge when below25% gross. Treaty refund is only the named route conditional on remittance, timely application and tax certificate; no blanket surcharge atop cap. Missing qualifications need information; unresolved anti-abuse/conflicts/AO42, comprehensive best-route questions (§44a(9), KStG32) need review. No gold results are tool context."""
p = HERE / "raw/implementation-rules.txt"
p.write_text(rules)
sources.append(
    dict(
        id="implementation-rules",
        title="Published curated implementation rules",
        url="https://www.gesetze-im-internet.de/estg/__43b.html",
        locator="Local implementation scope; linked primary law, not an official legal text",
        text="Implementation summary: " + rules,
        raw_path=str(p),
        sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        retrieved_at=records[0]["retrieved_at"],
        review_status="provisional",
    )
)
for filename, obj in [("cases.json", CASES), ("gold.json", GOLD), ("sources.json", sources)]:
    (HERE / filename).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
print(f"Wrote {len(CASES)} cases, {len(GOLD)} independent provisional rubrics, {len(sources)} sources.")
