import hashlib
import json
from pathlib import Path

import pytest
from tax_benchmark.models import CONFIGURATIONS, RunRequest
from test_budget_integration import priced
from test_runner import ANSWER, CASE, service_for


class RecordingProvider:
    def __init__(self):
        self.messages = []

    async def complete(self, model, messages):
        self.messages.append(json.loads(json.dumps(messages)))
        actions = [{"action": "case_facts"}, {"action": "read_source", "source_id": "law"},
                   {"action": "final", "answer": ANSWER}]
        return json.dumps(actions[(len(self.messages) - 1) % 3]), {"prompt_tokens": 10, "completion_tokens": 5}


def test_schema_is_a_fifth_separate_approach():
    ids = [item["id"] for item in CONFIGURATIONS]
    assert "typedb_schema" in ids
    request = RunRequest(case_ids=["case"], model_ids=["local"], configurations=ids)
    assert request.total_trials == 5


@pytest.mark.parametrize("harness", ["direct", "crewai"])
async def test_schema_reaches_provider_with_same_facts_and_tools_as_baseline(tmp_path, harness):
    provider = RecordingProvider()
    service = service_for(tmp_path, provider)
    schema = (Path(__file__).resolve().parents[1] / "typedb/schema.tql").read_bytes().decode()
    starts, contexts = {}, {}
    for arm in ["rag", "typedb_context", "typedb_schema", "typedb_functions", "sql"]:
        provider.messages.clear()
        trial = await service.trial("test", CASE, service.models["local"], arm, 1, 6, harness=harness)
        assert trial["passed"]
        starts[arm] = provider.messages[0]
        contexts[arm] = next(event["result"] for event in trial["trace"] if event.get("kind") == "tool")
    assert schema in starts["typedb_schema"][0]["content"]
    assert "fun decision_code" not in starts["typedb_schema"][0]["content"]
    assert starts["typedb_schema"][1:] == starts["rag"][1:]
    assert starts["typedb_schema"][0]["content"].startswith(starts["rag"][0]["content"])
    assert contexts["typedb_schema"] == contexts["rag"] == contexts["typedb_context"]
    assert "Available actions: case_facts, search_sources, read_source. " in starts["typedb_schema"][0]["content"]
    for arm in ["rag", "typedb_context", "typedb_functions", "sql"]:
        assert schema not in starts[arm][0]["content"]
    with pytest.raises(ValueError, match="unavailable"):
        await service.tool({"action": "evaluate_payment"}, CASE, "typedb_schema")


def test_schema_manifest_freezes_exact_text_hash_and_effective_prompt(tmp_path):
    service = service_for(tmp_path)
    request = RunRequest(case_ids=["case"], model_ids=["local"], configurations=["typedb_schema"])
    manifest = service.manifest(request)
    schema = (Path(__file__).resolve().parents[1] / "typedb/schema.tql").read_bytes()
    snapshot = manifest["schema_context"]
    assert snapshot["text"].encode() == schema
    assert snapshot["sha256"] == hashlib.sha256(schema).hexdigest()
    assert snapshot["system_prompt"] == service.system_prompt("typedb_schema", 6)
    assert "schema_context" not in service.manifest(request.model_copy(update={"configurations": ["rag"]}))


async def test_schema_change_blocks_resume_without_altering_the_original_run(tmp_path):
    service = service_for(tmp_path)
    run = await service.enqueue(RunRequest(case_ids=["case"], model_ids=["local"], configurations=["typedb_schema"]))
    run["status"] = "interrupted"
    service.store.save(run)
    service.schema_text += "\n# changed schema\n"
    with pytest.raises(ValueError, match="frozen"):
        await service.resume(run["id"])
    assert service.store.get(run["id"])["manifest"] == run["manifest"]


def test_schema_size_is_included_in_the_same_budget_reservation(tmp_path):
    service = service_for(tmp_path)
    priced(service)
    before = service.budget.snapshot()["reserved_eur"]
    service.budget.reserve_chat(service.models["local"], [{"role": "system", "content": service.system_prompt("rag", 6)}])
    baseline = service.budget.snapshot()["reserved_eur"] - before
    before = service.budget.snapshot()["reserved_eur"]
    service.budget.reserve_chat(service.models["local"], [{"role": "system", "content": service.system_prompt("typedb_schema", 6)}])
    assert service.budget.snapshot()["reserved_eur"] - before > baseline
