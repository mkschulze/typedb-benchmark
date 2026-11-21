import asyncio

import pytest
from tax_benchmark.models import RunRequest
from test_budget_integration import priced
from test_runner import CASE, FinalProvider, service_for


async def test_absolute_model_deadline_preserves_unknown_charge(tmp_path, monkeypatch):
    import tax_benchmark.runner as runner

    class Never:
        calls = 0

        async def complete(self, model, messages):
            self.calls += 1
            await asyncio.Event().wait()

    provider = Never()
    service = service_for(tmp_path, provider)
    priced(service)
    service.enforce_budget = True
    monkeypatch.setattr(runner, "MODEL_REQUEST_TIMEOUT_SECONDS", 0.01)
    trial = await service.trial("missing", CASE, service.models["local"], "rag", 1, 6)
    assert trial["status"] == "failed"
    assert "deadline" in trial["error"]
    assert provider.calls == 1
    assert trial["attempted"]
    assert trial["metrics"]["input_tokens"] is None
    assert service.budget.snapshot()["unreported_reservations"] == 1


async def test_explicit_recovery_preserves_charged_attempts_and_skips_their_keys(tmp_path):
    class Counting(FinalProvider):
        calls = 0

        async def complete(self, model, messages):
            self.calls += 1
            return await super().complete(model, messages)

    provider = Counting()
    original = service_for(tmp_path, provider)
    run = await original.enqueue(
        RunRequest(case_ids=["case"], model_ids=["local"], configurations=["rag", "sql"], repetitions=2)
    )
    completed = await original.trial(run["id"], CASE, original.models["local"], "rag", 1, 6)
    reservation = original.budget.reserve_usd(0.1, "chat:local")
    run = original.store.get(run["id"])
    run.update(status="interrupted", trials=[completed], completed_trials=1)
    run["active_trial"] = {
        "case_id": "case",
        "model_id": "local",
        "configuration": "sql",
        "repetition": 1,
        "status": "running",
        "metrics": {"input_tokens": 10, "output_tokens": 5, "wall_time_ms": 1},
        "trace": [
            {
                "step": 1,
                "kind": "model",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "content": '{"action":"case_facts"}',
            },
            {"step": 2, "kind": "budget", "reservation_id": reservation},
        ],
    }
    original.store.save(run)
    resumed = service_for(tmp_path, provider)
    resumed.start()
    try:
        await resumed.resume(run["id"])
        await asyncio.wait_for(resumed.queue.join(), 2)
        result = resumed.store.get(run["id"])
        assert result["status"] == "completed"
        assert len(result["trials"]) == 4
        assert provider.calls == 9
        keys = [(t["case_id"], t["model_id"], t["configuration"], t["repetition"]) for t in result["trials"]]
        assert len(set(keys)) == 4
        recovered = next(t for t in result["trials"] if t["configuration"] == "sql" and t["repetition"] == 1)
        assert recovered["status"] == "failed"
        assert recovered["metrics"]["input_tokens"] is None
        assert resumed.budget.snapshot()["unreported_reservations"] == 1
        assert result["continuations"][0]["unresolved_checkpoint_preserved_as_failed_attempt"]
    finally:
        await resumed.stop()


async def test_recovery_refuses_changed_frozen_inputs(tmp_path):
    service = service_for(tmp_path)
    run = await service.enqueue(RunRequest(case_ids=["case"], model_ids=["local"], configurations=["rag"]))
    run.update(status="interrupted")
    run["manifest"]["gold_sha256"] = "changed"
    service.store.save(run)
    with pytest.raises(ValueError, match="frozen"):
        await service.resume(run["id"])
    assert service.store.get(run["id"])["status"] == "interrupted"
