import asyncio
import json

import pytest
from tax_benchmark.models import RunRequest
from tax_benchmark.providers import ModelDefinition, ProviderError
from tax_benchmark.runner import RunService, comparison_estimates, grade_answer, measured_cost, usage_totals
from tax_benchmark.storage import RunStore


def test_grade_rejects_incorrect_amount_and_missing_evidence():
    gold = {"expected": {"total_withholding_cents": 2637500}, "required_source_ids": ["estg-50c"]}
    assert not grade_answer({"total_withholding_cents": 0, "source_ids": ["estg-50c"]}, gold)["passed"]
    assert not grade_answer({"total_withholding_cents": 2637500, "source_ids": []}, gold)["passed"]
    assert grade_answer({"total_withholding_cents": 2637500, "source_ids": ["estg-50c"]}, gold)["passed"]


def test_unreported_usage_stays_unknown():
    assert usage_totals([{}])["input_tokens"] is None
    usage = usage_totals(
        [{"prompt_tokens": 10, "completion_tokens": 5, "completion_tokens_details": {"reasoning_tokens": 3}}]
    )
    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 5
    assert usage["reasoning_tokens"] == 3


ANSWER = {
    "status": "determined",
    "relief_eligibility": "eligible",
    "relief_route": "section43b",
    "withholding_tax_cents": 25,
    "solidarity_surcharge_cents": 1,
    "total_withholding_cents": 26,
    "net_payment_cents": 74,
    "refund_status": "potential",
    "refund_amount_cents": 26,
    "missing_facts": [],
    "source_ids": ["law"],
    "evidence_ids": ["record"],
    "reasoning": "Source-supported test answer.",
}
CASE = {
    "id": "case",
    "question": "What is withheld?",
    "payment_date": "2026-06-30",
    "knowledge_date": "2026-06-30",
    "gross_amount_cents": 100,
    "documents": [{"id": "record"}],
    "template_group": "template",
}


class TestDatabase:
    def health(self):
        return {"available": True, "seeded": True}

    def context(self, case):
        return case

    def evaluate(self, case):
        return ANSWER


class FinalProvider:
    async def complete(self, model, messages):
        return json.dumps({"action": "final", "answer": ANSWER}), {
            "prompt_tokens": 10,
            "completion_tokens": 5,
        }


def service_for(tmp_path, provider=None):
    return RunService(
        RunStore(tmp_path / "run.sqlite"),
        [CASE],
        [{"id": "law", "title": "Law", "text": "Withholding law."}],
        {
            "case": {
                "expected": {"total_withholding_cents": 26},
                "required_source_ids": ["law"],
                "required_evidence_ids": ["record"],
            }
        },
        [ModelDefinition(id="local", name="Local", model="test", base_url="http://localhost:1234/v1")],
        TestDatabase(),
        lambda _: ANSWER,
        provider or FinalProvider(),
    )


async def test_run_persists_trials_and_complete_manifest(tmp_path):
    service = service_for(tmp_path)
    service.start()
    try:
        request = RunRequest(
            case_ids=["case"], model_ids=["local"], configurations=["rag", "sql"], repetitions=2
        )
        run = await service.enqueue(request)
        await asyncio.wait_for(service.queue.join(), 2)
        result = service.store.get(run["id"])
        assert result["status"] == "completed"
        assert result["completed_trials"] == 4
        assert all(trial["passed"] for trial in result["trials"])
        assert result["summary"][0]["avg_total_tokens"] == 15
        assert result["manifest"]["system_prompt"]
        assert "dataset_sha256" in result["manifest"]
        assert "api_key" not in json.dumps(result["manifest"])
    finally:
        await service.stop()


async def test_invalid_output_exhausts_budget_and_stays_in_denominator(tmp_path):
    class InvalidProvider:
        async def complete(self, model, messages):
            return "not JSON", {"prompt_tokens": 10, "completion_tokens": 5}

    service = service_for(tmp_path, InvalidProvider())
    trial = await service.trial("test", CASE, service.models["local"], "rag", 1, 2)
    assert not trial["passed"]
    assert trial["status"] == "failed"
    assert trial["metrics"]["input_tokens"] == 20
    assert len([item for item in trial["trace"] if item["kind"] == "repair"]) == 2


async def test_provider_failure_leaves_usage_unknown(tmp_path):
    class FailingProvider:
        async def complete(self, model, messages):
            raise ProviderError("Connection failed")

    service = service_for(tmp_path, FailingProvider())
    trial = await service.trial("test", CASE, service.models["local"], "rag", 1, 2)
    assert trial["status"] == "failed"
    assert trial["metrics"]["input_tokens"] is None


async def test_cancellation_stops_new_work_and_preserves_completed_calls(tmp_path):
    started, release = asyncio.Event(), asyncio.Event()

    class BlockingProvider:
        async def complete(self, model, messages):
            started.set()
            await release.wait()
            return json.dumps({"action": "final", "answer": ANSWER}), {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }

    service = service_for(tmp_path, BlockingProvider())
    service.start()
    try:
        run = await service.enqueue(
            RunRequest(case_ids=["case"], model_ids=["local"], configurations=["rag"], repetitions=3)
        )
        await asyncio.wait_for(started.wait(), 2)
        service.cancel(run["id"])
        release.set()
        await asyncio.wait_for(service.queue.join(), 2)
        result = service.store.get(run["id"])
        assert result["status"] == "cancelled"
        assert len(result["trials"]) == 1
        assert result["trials"][0]["metrics"]["input_tokens"] == 10
    finally:
        await service.stop()


def test_dated_prices_and_complete_usage_required_for_cost():
    model = ModelDefinition(
        id="p",
        name="Prices",
        model="test",
        input_price_per_million=2,
        output_price_per_million=8,
        price_date="2026-11-21",
    )
    assert measured_cost(
        model, {"input_tokens": 1000, "output_tokens": 100, "cached_tokens": 0}
    ) == pytest.approx(0.0028)
    assert measured_cost(model, {"input_tokens": None, "output_tokens": 100}) is None
    assert measured_cost(model, {"input_tokens": 1000, "output_tokens": 100, "cached_tokens": 500}) is None


def test_identical_paired_outcomes_have_zero_difference():
    trials = [
        {"case_id": key, "model_id": "m", "configuration": arm, "passed": passed, "repetition": 1}
        for key, passed in [("a", True), ("b", False)]
        for arm in ["rag", "sql"]
    ]
    cases = {"a": {"template_group": "a"}, "b": {"template_group": "b"}}
    estimate = comparison_estimates(trials, cases)[0]
    assert estimate["difference"] == 0
    assert estimate["ci95"] == [0, 0]


async def test_cancelled_queued_run_does_not_start_setup(tmp_path):
    started, release = asyncio.Event(), asyncio.Event()

    class BlockingProvider:
        async def complete(self, model, messages):
            started.set()
            await release.wait()
            return json.dumps({"action": "final", "answer": ANSWER}), {}

    service = service_for(tmp_path, BlockingProvider())
    preparations = []

    async def prepare():
        preparations.append(True)

    service.retriever.prepare = prepare
    service.start()
    try:
        request = RunRequest(case_ids=["case"], model_ids=["local"], configurations=["rag"])
        await service.enqueue(request)
        await asyncio.wait_for(started.wait(), 2)
        queued = await service.enqueue(request)
        service.cancel(queued["id"])
        release.set()
        await asyncio.wait_for(service.queue.join(), 2)
        assert len(preparations) == 1
        assert service.store.get(queued["id"])["status"] == "cancelled"
    finally:
        await service.stop()


async def test_restart_keeps_partial_trace_without_replaying_calls(tmp_path):
    waiting = asyncio.Event()

    class PartialProvider:
        calls = 0

        async def complete(self, model, messages):
            self.calls += 1
            if self.calls == 1:
                return '{"action":"case_facts"}', {"prompt_tokens": 10, "completion_tokens": 5}
            waiting.set()
            await asyncio.Event().wait()

    provider = PartialProvider()
    service = service_for(tmp_path, provider)
    service.start()
    run = await service.enqueue(RunRequest(case_ids=["case"], model_ids=["local"], configurations=["rag"]))
    await asyncio.wait_for(waiting.wait(), 2)
    await service.stop()
    restarted = service_for(tmp_path, provider)
    restarted.start()
    try:
        saved = restarted.store.get(run["id"])
        assert saved["status"] == "interrupted"
        assert len(saved["active_trial"]["trace"]) == 2
        assert saved["active_trial"]["metrics"]["input_tokens"] == 10
        assert not saved["active_trial"]["usage_complete"]
        assert provider.calls == 2
    finally:
        await restarted.stop()
