import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def domain():
    assert (ROOT / "backend/tax_benchmark/domain.py").exists(), "The public domain module is missing"
    from tax_benchmark import domain as module

    return module


def test_frozen_dataset_has_disjoint_templates_and_separate_gold():
    module = domain()
    cases, gold, sources = module.load_cases(), module.load_gold(), module.load_sources()
    assert len(cases) == 40
    assert sum(c["split"] == "development" for c in cases) == 10
    assert sum(c["split"] == "evaluation" for c in cases) == 30
    templates = {
        s: {c["template_group"] for c in cases if c["split"] == s} for s in ("development", "evaluation")
    }
    assert not templates["development"] & templates["evaluation"]
    assert len({c["category"] for c in cases}) == 6
    for case in cases:
        assert "expected" not in case and "answer" not in case
        assert case["review_status"] == gold[case["id"]]["review_status"] == "provisional"
        answer = module.sql_answer(case)
        for field, expected in gold[case["id"]]["expected"].items():
            assert answer[field] == expected, (case["id"], field, answer[field], expected)
        assert set(answer["source_ids"]) <= {s["id"] for s in sources}
        assert set(answer["evidence_ids"]) <= {d["id"] for d in case["documents"]}


def test_gold_grades_the_exact_requested_relief_route():
    module = domain()
    gold = module.load_gold()
    for case in module.load_cases():
        assert gold[case["id"]]["expected"].get("relief_route") == case["facts"]["requested_route"]


def test_counterfactual_certificate_variants_share_one_evaluation_group():
    cases = {case["id"]: case for case in domain().load_cases()}
    variants = [
        cases[id_]
        for id_ in (
            "dev-01",
            "dev-02",
            "dev-06",
            "eval-11",
            "eval-12",
            "eval-13",
            "eval-14",
            "eval-15",
            "eval-24",
            "eval-25",
            "eval-26",
        )
    ]
    assert len({case["template_group"] for case in variants}) == 1
    assert {case["split"] for case in variants} == {"evaluation"}
    development = [case for case in cases.values() if case["split"] == "development"]
    assert {case["template_group"] for case in development} == {"domestic_math", "company_qualification"}


def test_source_paths_and_regenerated_fixtures_work_in_a_relocated_checkout(tmp_path):
    for source in domain().load_sources():
        assert not Path(source["raw_path"]).is_absolute(), source["id"]
    relocated = tmp_path / "relocated-checkout"
    shutil.copytree(ROOT / "data", relocated / "data")
    shutil.copytree(ROOT / "backend/tax_benchmark", relocated / "backend/tax_benchmark")
    subprocess.run([sys.executable, str(relocated / "data/build_dataset.py")], cwd=tmp_path, check=True)
    check = """
import hashlib
from tax_benchmark.domain import ROOT, load_sources
for source in load_sources():
    from pathlib import Path
    assert not Path(source['raw_path']).is_absolute()
    assert hashlib.sha256((ROOT/source['raw_path']).read_bytes()).hexdigest() == source['sha256']
"""
    subprocess.run(
        [sys.executable, "-c", check],
        cwd=tmp_path,
        check=True,
        env={**os.environ, "PYTHONPATH": str(relocated / "backend")},
    )


def test_certificate_changes_payment_but_not_entitlement():
    module = domain()
    cases = {c["id"]: c for c in module.load_cases()}
    without = module.sql_answer(cases["dev-01"])
    issued = module.sql_answer(cases["dev-02"])
    assert without["relief_eligibility"] == issued["relief_eligibility"] == "eligible"
    assert without["withholding_tax_cents"] == 2_500_000
    assert without["solidarity_surcharge_cents"] == 137_500
    assert without["total_withholding_cents"] == 2_637_500
    assert without["refund_amount_cents"] == 2_637_500
    assert issued["total_withholding_cents"] == 0


def test_missing_inventory_is_not_absent_certificate():
    module = domain()
    case = next(c for c in module.load_cases() if c["id"] == "eval-26")
    answer = module.sql_answer(case)
    assert answer["status"] == "needs_information"
    assert answer["withholding_tax_cents"] is None
    assert "certificate_inventory_complete" in answer["missing_facts"]


def test_sources_preserve_original_bytes_and_hashes():
    for source in domain().load_sources():
        assert "Summary" in source["text"] or "Implementation" in source["text"]
        raw = ROOT / source["raw_path"]
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == source["sha256"]
        assert source["retrieved_at"]
        assert source["url"].startswith("https://")


def test_reference_is_labelled_and_all_money_is_integer_or_unknown():
    module = domain()
    case = module.load_cases()[0]
    answer = module.reference_answer(case)
    assert answer["calculation_backend"] == "sql_reference"
    assert answer["review_status"] == "provisional"
    for field in (
        "withholding_tax_cents",
        "solidarity_surcharge_cents",
        "total_withholding_cents",
        "net_payment_cents",
        "refund_amount_cents",
    ):
        assert answer[field] is None or type(answer[field]) is int
    json.dumps(answer)


def test_unsupported_attribution_and_conflicting_records_do_not_silently_compute_relief():
    from copy import deepcopy

    module = domain()
    case = deepcopy(module.load_cases()[0])
    case["facts"]["permanent_establishment_attribution"] = True
    assert module.sql_answer(case)["status"] == "outside_scope"
    case["facts"]["permanent_establishment_attribution"] = False
    case["facts"]["records_conflict"] = True
    assert module.sql_answer(case)["status"] == "review_required"


def test_fractional_tax_cent_requires_review_and_future_knowledge_requests_facts():
    from copy import deepcopy

    module = domain()
    case = deepcopy(module.load_cases()[0])
    case["gross_amount_cents"] = 101
    assert module.sql_answer(case)["status"] == "review_required"
    assert module.sql_answer(case)["withholding_tax_cents"] is None
    case["gross_amount_cents"] = 100_000
    case["knowledge_date"] = "2026-01-01"
    assert module.sql_answer(case)["status"] == "needs_information"
    assert module.sql_answer(case)["missing_facts"] == ["payment_time_facts"]


def test_treaty_certificate_cannot_bypass_section50c_direct_participation_requirement():
    from copy import deepcopy

    module = domain()
    case = deepcopy(next(c for c in module.load_cases() if c["id"] == "dev-07"))
    case["facts"]["direct_holding_basis_points"] = 900
    case["facts"]["resolution_holding_basis_points"] = 900
    answer = module.sql_answer(case)
    assert answer["relief_eligibility"] == "eligible"
    assert answer["withholding_tax_cents"] == 2_500_000
    assert answer["refund_amount_cents"] == 1_137_500
