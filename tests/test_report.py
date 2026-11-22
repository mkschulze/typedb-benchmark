import pytest
from tax_benchmark.report import summarize


def trial(configuration, case_id, checks, error=None, tokens=(100, 10), wall=1000):
    metrics = {"input_tokens": tokens[0], "output_tokens": tokens[1], "wall_time_ms": wall} if tokens else {}
    return {"model_id": "m", "configuration": configuration, "case_id": case_id, "repetition": 1,
            "grading": {"checks": checks} if checks is not None else None, "error": error, "metrics": metrics}


def test_summary_counts_decision_fields_errors_and_measured_pairs():
    decision_and_evidence = {"status": True, "relief_route": True, "required_sources": False}
    run = {
        "id": "r", "status": "completed", "total_trials": 4,
        "request": {"model_ids": ["m"], "configurations": ["rag", "sql"], "case_ids": ["a", "b"], "repetitions": 1},
        "manifest": {"dataset_sha256": "d", "sources_sha256": "s", "gold_sha256": "g",
                     "models": [{"id": "m", "max_output_tokens": 2048}]},
        "summary": [{"model_id": "m", "configuration": "rag"}, {"model_id": "m", "configuration": "sql"}],
        "comparisons": [],
        "trials": [
            trial("rag", "a", decision_and_evidence),          # decision right, evidence wrong
            trial("rag", "b", {"status": True}),                # relief_route missing: counts as failed
            trial("sql", "a", decision_and_evidence, tokens=(40, 10), wall=500),
            trial("sql", "b", None, error="No answer", tokens=None),  # unmeasured: excluded from pairs
        ],
    }

    result = summarize(run)

    rag, sql = result["rows"]
    assert rag["decision_fields_pass"] == 1 and sql["decision_fields_pass"] == 1
    assert sql["errors_by_message"] == {"No answer": 1}
    [pair] = result["efficiency_paired"]
    assert pair["configuration"] == "sql" and pair["fully_measured_pairs"] == 1
    assert pair["token_reduction_fraction"] == pytest.approx(1 - 50 / 110)
    assert pair["wall_time_reduction_fraction"] == pytest.approx(0.5)
    assert result["max_output_tokens"] == {"m": 2048}
    assert "schema_sha256" not in result["frozen_inputs"]
