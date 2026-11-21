"""Real TypeDB 3 driver integration. Unavailability is explicit; no fallback evaluator."""

import json
import os

from typedb.driver import Credentials, DriverOptions, DriverTlsConfig, TransactionType, TypeDB

from .domain import ROOT, format_answer

TRI_STATE = (
    "payer_unlimited_taxable",
    "recipient_eu_resident",
    "recipient_qualifying_form",
    "recipient_subject_to_tax",
    "beneficial_owner",
    "permanent_establishment_attribution",
    "ownership_continuous",
    "owners_entitled",
    "economic_link",
    "listed_exception",
    "main_purpose_exception",
    "ao42_concern",
    "certificate_inventory_complete",
    "records_conflict",
)


def literal(value):
    return json.dumps(value, ensure_ascii=False)


def day(value):
    # TypeQL date arithmetic requires datetime; all case dates are calendar dates at midnight.
    from datetime import date

    return date.fromisoformat(value).isoformat() + "T00:00:00"


class TypeDBStore:
    def __init__(self):
        self.address = os.getenv("TYPEDB_ADDRESS", "localhost:1730")
        self.username = os.getenv("TYPEDB_USERNAME", "admin")
        self.password = os.getenv("TYPEDB_PASSWORD", "password")
        self.database = os.getenv("TYPEDB_DATABASE", "dividend_benchmark")

    def _driver(self):
        return TypeDB.driver(
            self.address,
            Credentials(self.username, self.password),
            DriverOptions(DriverTlsConfig.disabled(), request_timeout_millis=5000),
        )

    @staticmethod
    def _query(tx, query):
        answer = tx.query(query).resolve()
        if answer.is_concept_documents():
            return list(answer.as_concept_documents())
        if answer.is_concept_rows():
            list(answer.as_concept_rows())
        return []

    def health(self) -> dict:
        try:
            with self._driver() as driver:
                present = driver.databases.contains(self.database)
                count = 0
                if present:
                    with driver.transaction(self.database, TransactionType.READ) as tx:
                        rows = self._query(
                            tx, 'match $c isa dividend_case; reduce $count = count; fetch {"count": $count};'
                        )
                        count = rows[0]["count"] if rows else 0
                return dict(
                    status="ok",
                    available=True,
                    seeded=count > 0,
                    database=self.database,
                    message=f"TypeDB connected; {count} cases stored.",
                    case_count=count,
                )
        except Exception as exc:
            # Do not expose connection errors containing credentials to the public health endpoint.
            return dict(
                status="unavailable",
                available=False,
                seeded=False,
                database=self.database,
                message=f"TypeDB connection/schema unavailable ({type(exc).__name__}).",
            )

    def seed(self, cases: list[dict]) -> None:
        with self._driver() as driver:
            if not driver.databases.contains(self.database):
                driver.databases.create(self.database)
            schema = driver.databases.get(self.database).type_schema()
            if "dividend_case" not in schema:
                with driver.transaction(self.database, TransactionType.SCHEMA) as tx:
                    tx.query((ROOT / "typedb/schema.tql").read_text()).resolve()
                    tx.query((ROOT / "typedb/functions.tql").read_text()).resolve()
                    tx.commit()
            else:
                with driver.transaction(self.database, TransactionType.SCHEMA) as tx:
                    functions = (ROOT / "typedb/functions.tql").read_text()
                    tx.query(functions.replace("define\n", "redefine\n", 1)).resolve()
                    tx.commit()
            for case in cases:
                with driver.transaction(self.database, TransactionType.READ) as tx:
                    previous = self._query(
                        tx,
                        f'match $c isa dividend_case, has case_id {literal(case["id"])}; fetch {{"payload": $c.record_payload}};',
                    )
                payload = json.dumps(case, ensure_ascii=False, sort_keys=True)
                if previous and previous[0]["payload"] == payload:
                    continue
                with driver.transaction(self.database, TransactionType.WRITE) as tx:
                    if previous:
                        self._query(
                            tx,
                            f"match $c isa dividend_case, has case_id {literal(case['id'])}; "
                            "$r isa case_document, links (case_record: $c, document: $d); delete $r; $d;",
                        )
                        self._query(
                            tx, f"match $c isa dividend_case, has case_id {literal(case['id'])}; delete $c;"
                        )
                    self._query(tx, self._insert(case, payload))
                    tx.commit()

    @staticmethod
    def _insert(case, payload):
        facts = case["facts"]
        attributes = [
            ("case_id", literal(case["id"])),
            ("record_payload", literal(payload)),
            ("gross_cents", str(case["gross_amount_cents"])),
            ("payment_day", day(case["payment_date"])),
            ("knowledge_day", day(case["knowledge_date"])),
            ("payer_id", literal(case["payer"]["id"])),
            ("recipient_id", literal(case["recipient"]["id"])),
            ("payer_country", literal(case["payer"]["country"])),
            ("payer_form", literal(case["payer"].get("legal_form", "unknown"))),
            ("recipient_country", literal(case["recipient"]["country"])),
        ]
        for key in ("requested_route", "distribution_kind", "recipient_kind"):
            attributes.append((key, literal(facts.get(key, "unknown"))))
        for key in TRI_STATE:
            value = facts.get(key)
            attributes.append(
                (key, literal("yes" if value is True else "no" if value is False else "unknown"))
            )
        for key in ("direct_holding_basis_points", "resolution_holding_basis_points"):
            value = facts.get(key)
            attributes.append((key, str(-1 if value is None else value)))
        if facts.get("ownership_since"):
            attributes.append(("ownership_since", day(facts["ownership_since"])))
        attributes.extend(("source_id", literal(s)) for s in case["source_ids"])
        query = "insert $c isa dividend_case, " + ", ".join(f"has {k} {v}" for k, v in attributes) + ";\n"
        for index, document in enumerate(case["documents"]):
            variable = f"$doc{index}"
            certificate = document.get("kind") == "bzst_exemption"
            attrs = [
                ("evidence_id", literal(document["id"])),
                ("evidence_payload", literal(json.dumps(document, ensure_ascii=False, sort_keys=True))),
            ]
            if certificate:
                attrs.extend(
                    [
                        ("certificate_route", literal(document["route"])),
                        ("certificate_issue_day", day(document["issued_at"])),
                        ("certificate_available_day", day(document["available_at"])),
                        ("certificate_start_day", day(document["valid_from"])),
                        ("certificate_end_day", day(document["valid_until"])),
                        ("certificate_payer_id", literal(document["payer_id"])),
                        ("certificate_recipient_id", literal(document["recipient_id"])),
                        ("certificate_revoked", literal(document["revoked"])),
                    ]
                )
            query += (
                f"{variable} isa {'exemption_certificate' if certificate else 'evidence_document'}, "
                + ", ".join(f"has {k} {v}" for k, v in attrs)
                + ";\n"
            )
            query += f"case_document(case_record: $c, document: {variable});\n"
        return query

    def _stored_case(self, tx, case):
        rows = self._query(
            tx,
            f'match $c isa dividend_case, has case_id {literal(case["id"])}; fetch {{"payload": $c.record_payload}};',
        )
        if not rows:
            raise RuntimeError("TypeDB case is not seeded; run the explicit seed command first.")
        stored = json.loads(rows[0]["payload"])
        if stored != case:
            raise RuntimeError(
                "TypeDB case facts differ from the requested frozen fixture; reseed before running."
            )
        return stored

    def context(self, case: dict) -> dict:
        with self._driver() as driver:
            with driver.transaction(self.database, TransactionType.READ) as tx:
                stored = self._stored_case(tx, case)
                fact_fields = (
                    *TRI_STATE,
                    "requested_route",
                    "distribution_kind",
                    "recipient_kind",
                    "direct_holding_basis_points",
                    "resolution_holding_basis_points",
                    "ownership_since",
                )
                projection = ", ".join(f'"{key}": $c.{key}' for key in fact_fields)
                graph = self._query(
                    tx,
                    f"match $c isa dividend_case, has case_id {literal(case['id'])}; "
                    'fetch {"facts": {' + projection + '}, "source_ids": [$c.source_id]};',
                )[0]
                rows = self._query(
                    tx,
                    f'match $c isa dividend_case, has case_id {literal(case["id"])}; case_document(case_record: $c, document: $d); fetch {{"payload": $d.evidence_payload}};',
                )
        documents = {d["id"]: d for d in (json.loads(row["payload"]) for row in rows)}
        facts = graph["facts"]
        for field in TRI_STATE:
            facts[field] = {"yes": True, "no": False, "unknown": None}[facts[field]]
        if facts["ownership_since"] is not None:
            facts["ownership_since"] = facts["ownership_since"][:10]
        for field in ("direct_holding_basis_points", "resolution_holding_basis_points"):
            if facts[field] == -1:
                facts[field] = None
        return dict(
            case_id=stored["id"],
            gross_amount_cents=stored["gross_amount_cents"],
            payment_date=stored["payment_date"],
            knowledge_date=stored["knowledge_date"],
            payer=stored["payer"],
            recipient=stored["recipient"],
            facts=facts,
            documents=[documents[d["id"]] for d in stored["documents"]],
            source_ids=sorted(graph["source_ids"]),
            review_status="provisional",
            backend="typedb_context",
        )

    def evaluate(self, case: dict) -> dict:
        prefix = f"match $c isa dividend_case, has case_id {literal(case['id'])}; "
        with self._driver() as driver:
            with driver.transaction(self.database, TransactionType.READ) as tx:
                stored = self._stored_case(tx, case)
                decisions = self._query(
                    tx, prefix + 'let $code in decision_code($c); fetch {"decision_code": $code};'
                )
                if len(decisions) != 1:
                    raise RuntimeError(
                        f"TypeDB decision function returned {len(decisions)} outcomes; expected exactly one."
                    )
                result = decisions[0]
                amounts = self._query(
                    tx,
                    prefix
                    + 'let $tax, $surcharge, $total, $net in payment_amounts($c); fetch {"tax_cents": $tax, "surcharge_cents": $surcharge, "total_cents": $total, "net_cents": $net};',
                )
                if amounts:
                    result.update(amounts[0])
                refunds = self._query(
                    tx, prefix + 'let $refund in refund_amount($c); fetch {"refund_cents": $refund};'
                )
                if refunds:
                    result.update(refunds[0])
                missing = self._query(
                    tx, prefix + 'let $field in missing_qualification($c); fetch {"field": $field};'
                )
                provenance = self._query(
                    tx,
                    prefix + 'fetch {"sources": [$c.source_id], "evidence": '
                    '[match case_document(case_record: $c, document: $d); fetch {"id": $d.evidence_id};]};',
                )[0]
                result["missing_facts"] = sorted(row["field"] for row in missing)
                if result["decision_code"] == 9:
                    result["missing_facts"] = ["certificate_inventory_complete"]
                elif result["decision_code"] == 10:
                    result["missing_facts"] = ["payment_time_facts"]
        answer = format_answer(stored, result, "typedb_functions")
        answer["source_ids"] = sorted(provenance["sources"])
        answer["evidence_ids"] = sorted(item["id"] for item in provenance["evidence"])
        return answer
