"""Turn a run export into the measured part of a `results/*.json` summary."""

from collections import Counter

EVIDENCE_CHECKS = {"required_sources", "required_evidence", "cited_sources_retrieved", "cited_evidence_retrieved"}


def _total_tokens(trial):
    metrics = trial.get("metrics") or {}
    if metrics.get("input_tokens") is None or metrics.get("output_tokens") is None:
        return None
    return metrics["input_tokens"] + metrics["output_tokens"]


def rows(run):
    # a check absent from a trial counts as failed
    decision_checks = sorted(
        {key for trial in run["trials"] if trial.get("grading") for key in trial["grading"]["checks"]}
        - EVIDENCE_CHECKS
    )
    result = []
    for row in run["summary"]:
        trials = [t for t in run["trials"]
                  if t["model_id"] == row["model_id"] and t["configuration"] == row["configuration"]]
        decision_pass = sum(
            1 for t in trials
            if t.get("grading") and all(t["grading"]["checks"].get(key) for key in decision_checks)
        )
        errors = Counter(t["error"] for t in trials if t.get("error"))
        result.append({**row, "decision_fields_pass": decision_pass, "errors_by_message": dict(errors)})
    return result


def efficiency(run, baseline="rag"):
    """Paired token and wall-time reductions against the baseline, over pairs with both measured."""
    result = []
    for model_id in run["request"]["model_ids"]:
        def by_key(configuration):
            return {(t["case_id"], t["repetition"]): t for t in run["trials"]
                    if t["model_id"] == model_id and t["configuration"] == configuration}

        base = by_key(baseline)
        for configuration in run["request"]["configurations"]:
            if configuration == baseline:
                continue
            arm = by_key(configuration)
            pairs = [(base[key], arm[key]) for key in base
                     if key in arm and _total_tokens(base[key]) is not None and _total_tokens(arm[key]) is not None]
            if not pairs:
                continue
            base_tokens = sum(_total_tokens(b) for b, _ in pairs) / len(pairs)
            arm_tokens = sum(_total_tokens(a) for _, a in pairs) / len(pairs)
            base_time = sum(b["metrics"]["wall_time_ms"] for b, _ in pairs) / len(pairs)
            arm_time = sum(a["metrics"]["wall_time_ms"] for _, a in pairs) / len(pairs)
            result.append({
                "model_id": model_id, "baseline": baseline, "configuration": configuration,
                "fully_measured_pairs": len(pairs),
                "mean_baseline_total_tokens": base_tokens, "mean_configuration_total_tokens": arm_tokens,
                "token_reduction_fraction": 1 - arm_tokens / base_tokens,
                "wall_time_reduction_fraction": 1 - arm_time / base_time,
            })
    return result


def summarize(run, baseline="rag"):
    manifest = run["manifest"]
    frozen = {key: manifest[key] for key in ("dataset_sha256", "sources_sha256", "gold_sha256")}
    if manifest.get("schema_context"):
        frozen["schema_sha256"] = manifest["schema_context"]["sha256"]
    return {
        "run_id": run["id"],
        "status": run["status"],
        "harness": run["request"].get("harness", "direct"),
        "case_count": len(run["request"]["case_ids"]),
        "attempts": run["total_trials"],
        "repetitions": run["request"]["repetitions"],
        "max_output_tokens": {model["id"]: model.get("max_output_tokens") for model in manifest["models"]},
        "rows": rows(run),
        "efficiency_paired": efficiency(run, baseline),
        "comparisons": run["comparisons"],
        "frozen_inputs": frozen,
    }
