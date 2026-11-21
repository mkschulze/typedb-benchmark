"""Frozen public facts and provisional reference formatting; gold is never tool context."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def load_cases() -> list[dict]:
    return json.loads((DATA_DIR / "cases.json").read_text())


def load_sources() -> list[dict]:
    return json.loads((DATA_DIR / "sources.json").read_text())


def load_gold() -> dict:
    return json.loads((DATA_DIR / "gold.json").read_text())


REASONS = {
    0: "Domestic withholding only: 25% capital income tax plus 5.5% of that tax, discarding fractional surcharge cents. Substantive relief and refunds were not requested.",
    1: "Substantive relief is established for the requested route. No matching issued BZSt exemption was available at payment, so domestic withholding applies. The stated refund is potential on timely valid application, remittance and tax certificate.",
    2: "A matching issued BZSt exemption was available and valid at payment and the substantive conditions are established. Apply its supported relief route. A treaty reduction applies to surcharge first; no surcharge is added above the combined treaty cap.",
    3: "The explicitly requested relief route fails a modeled condition. Domestic withholding applies. This does not deny other treaty or domestic refund routes outside the question.",
    4: "The uninterrupted twelve-month period is not yet completed as of the knowledge date. Domestic withholding applies; §43b may permit a refund after completion. Relief at payment cannot be assumed.",
    5: "The twelve-month period completed after payment but by the knowledge date. §43b(2) provides the later refund route and excludes exemption at payment in this situation. Refund remains conditional on procedure.",
    6: "A necessary substantive fact is unknown. Request the listed information; an unknown is not a negative fact. Known absence of payment-time exemption still requires domestic withholding.",
    7: "Legal review is required: unresolved anti-abuse/AO §42 or record conflict, or a comprehensive relief request requiring §44a(9) and KStG §32 as well as the named routes. No exhaustive refund conclusion is automated.",
    8: "Outside supported scope: ordinary cash dividends from a German GmbH to a Netherlands corporation during the 2026 source snapshot. No simplified outcome is applied.",
    9: "The payment-time certificate inventory is not confirmed complete and no qualifying certificate is established. Obtain the inventory; unknown certificate status does not establish full or zero withholding.",
    10: "The knowledge cutoff precedes payment. The actual payment-time facts are not yet established; obtain the payment-time record.",
    11: "The ordinary-dividend tax base produces a fractional cent or unsupported ownership continuity. The frozen mechanical scope requires legal review of this calculation or record.",
}


def format_answer(case: dict, result: dict, backend: str) -> dict:
    """Format database outputs without applying tax decision rules in Python."""
    code = int(result["decision_code"])
    status = (
        "needs_information"
        if code in (6, 9, 10)
        else "review_required"
        if code in (7, 11)
        else "outside_scope"
        if code == 8
        else "determined"
    )
    eligibility = "eligible" if code in (1, 2, 5, 9) else "ineligible" if code == 3 else "undetermined"
    refund_status = {
        0: "not_assessed",
        1: "potential_on_application",
        2: "not_needed",
        3: "unavailable_under_requested_route",
        4: "conditional_on_holding_completion",
        5: "potential_on_application",
        6: "undetermined",
        7: "requires_review",
        8: "not_assessed",
        9: "undetermined",
        10: "undetermined",
        11: "requires_review",
    }[code]
    return dict(
        status=status,
        relief_eligibility=eligibility,
        relief_route=case["facts"].get("requested_route", "undetermined"),
        withholding_tax_cents=result.get("tax_cents"),
        solidarity_surcharge_cents=result.get("surcharge_cents"),
        total_withholding_cents=result.get("total_cents"),
        net_payment_cents=result.get("net_cents"),
        refund_status=refund_status,
        refund_amount_cents=result.get("refund_cents"),
        missing_facts=result.get("missing_facts", []),
        source_ids=list(case["source_ids"]),
        evidence_ids=[d["id"] for d in case["documents"]],
        reasoning=REASONS[code],
        review_status="provisional",
        calculation_backend=backend,
    )


def sql_answer(case: dict) -> dict:
    from .sql_control import evaluate_sql

    return format_answer(case, evaluate_sql(case), "sql_control")


def reference_answer(case: dict) -> dict:
    from .sql_control import evaluate_sql

    answer = format_answer(case, evaluate_sql(case), "sql_reference")
    answer["reasoning"] = (
        "Provisional deterministic reference walkthrough; not a measured LLM result. " + answer["reasoning"]
    )
    return answer
