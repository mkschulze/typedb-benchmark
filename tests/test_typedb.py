import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.getenv("RUN_TYPEDB_INTEGRATION") != "1",
    reason="Set RUN_TYPEDB_INTEGRATION=1 with the dedicated TypeDB server running",
)
def test_real_typedb_functions_match_independent_provisional_gold():
    assert (ROOT / "backend/tax_benchmark/typedb_store.py").exists(), "Real TypeDB adapter is missing"
    from tax_benchmark.domain import load_cases, load_gold, sql_answer
    from tax_benchmark.typedb_store import TypeDBStore

    store = TypeDBStore()
    cases, gold = load_cases(), load_gold()
    store.seed(cases)
    assert store.health()["status"] == "ok"
    for case in cases:
        answer = store.evaluate(case)
        assert answer["calculation_backend"] == "typedb_functions"
        for key, expected in gold[case["id"]]["expected"].items():
            assert answer[key] == expected, (case["id"], key, answer[key], expected)
            assert answer[key] == sql_answer(case)[key]
        context = store.context(case)
        assert context["facts"] == case["facts"]
        assert "answer" not in context and "total_withholding_cents" not in context
        assert context["documents"] == case["documents"]
        assert set(answer["source_ids"]) == set(case["source_ids"])
        assert set(answer["evidence_ids"]) == {d["id"] for d in case["documents"]}


@pytest.mark.skipif(os.getenv("RUN_TYPEDB_INTEGRATION") != "1", reason="Requires the dedicated TypeDB server")
def test_reseeding_changed_fixture_replaces_relations_and_restores_original():
    from copy import deepcopy

    from tax_benchmark.domain import load_cases
    from tax_benchmark.typedb_store import TypeDBStore

    store = TypeDBStore()
    original = load_cases()[0]
    updated = deepcopy(original)
    updated["facts"]["direct_holding_basis_points"] = 500
    updated["facts"]["resolution_holding_basis_points"] = 500
    try:
        store.seed([updated])
        assert store.context(updated)["facts"]["direct_holding_basis_points"] == 500
        assert store.evaluate(updated)["relief_eligibility"] == "ineligible"
        with pytest.raises(RuntimeError, match="differ"):
            store.evaluate(original)
    finally:
        store.seed([original])
