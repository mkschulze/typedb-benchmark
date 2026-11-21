import asyncio
import importlib.util
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError
from tax_benchmark.budget import BudgetError
from tax_benchmark.models import TaxAnswer

pytestmark = pytest.mark.skipif(importlib.util.find_spec("crewai") is None, reason="CrewAI extra not installed")

QUESTION = {
    "case_id": "case",
    "question": "What is withheld?",
    "payment_date": "2026-06-30",
    "knowledge_date": "2026-06-30",
}
ANSWER = {
    "status": "determined",
    "relief_eligibility": "eligible",
    "relief_route": "section43b",
    "withholding_tax_cents": 25,
    "solidarity_surcharge_cents": 1,
    "total_withholding_cents": 26,
    "net_payment_cents": 74,
    "refund_status": "potential_on_application",
    "refund_amount_cents": 26,
    "missing_facts": [],
    "source_ids": ["law"],
    "evidence_ids": ["record"],
    "reasoning": "Source-supported test answer.",
}
TOOLS = {"case_facts", "search_sources", "read_source"}


async def test_actual_crewai_runs_two_tools_and_returns_final_json(monkeypatch):
    from tax_benchmark.crewai_harness import run_crewai

    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    messages_seen, actions, events = [], [], []
    responses = iter([
        {"action": "case_facts"},
        {"action": "read_source", "source_id": "law"},
        {"action": "final", "answer": ANSWER},
    ])

    async def complete(messages):
        messages_seen.append(deepcopy(messages))
        return json.dumps(next(responses))

    async def tool(action):
        actions.append(action)
        if action["action"] == "case_facts":
            return {"documents": [{"id": "record", "text": "Payment evidence from host tool."}]}
        return {"id": "law", "text": "Withholding law from host tool."}

    result = await run_crewai(
        system_prompt="Return one JSON action per turn. Use supplied evidence.",
        question=QUESTION,
        max_steps=3,
        complete=complete,
        tool=tool,
        available_tools=TOOLS,
        event=events.append,
    )
    assert json.loads(result) == ANSWER
    assert actions == [{"action": "case_facts"}, {"action": "read_source", "source_id": "law"}]
    assert len(messages_seen) == 3
    assert messages_seen[0][0] == {
        "role": "system", "content": "Return one JSON action per turn. Use supplied evidence."
    }
    assert QUESTION["question"] in json.dumps(messages_seen[0])
    assert "Payment evidence from host tool." in json.dumps(messages_seen[1])
    assert "Withholding law from host tool." in json.dumps(messages_seen[2])
    assert "Action: case_facts" in json.dumps(messages_seen[1])
    assert any(event.get("framework") == "crewai" for event in events)


async def test_unavailable_evaluation_tool_never_reaches_host():
    from tax_benchmark.crewai_harness import run_crewai

    actions, prompts = [], []
    responses = iter([{"action": "evaluate_payment"}, {"action": "final", "answer": ANSWER}])

    async def complete(messages):
        prompts.append(deepcopy(messages))
        return json.dumps(next(responses))

    async def tool(action):
        actions.append(action)
        return {}

    result = await run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=2, complete=complete, tool=tool, available_tools=TOOLS,
    )
    assert json.loads(result) == ANSWER
    assert not actions
    assert "evaluate_payment" not in json.dumps(prompts[0])


async def test_executable_arm_registers_evaluation_tool():
    from tax_benchmark.crewai_harness import run_crewai

    actions = []
    responses = iter([{"action": "evaluate_payment"}, {"action": "final", "answer": ANSWER}])

    async def complete(messages):
        return json.dumps(next(responses))

    async def tool(action):
        actions.append(action)
        return {"decision": ANSWER}

    result = await run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=2, complete=complete, tool=tool,
        available_tools=TOOLS | {"evaluate_payment"},
    )
    assert json.loads(result) == ANSWER
    assert actions == [{"action": "evaluate_payment"}]


@pytest.mark.parametrize("invalid", ["not JSON", "[]", '{"action":[]}', '{"action":"final","answer":[]}'])
async def test_invalid_output_can_be_repaired_by_crewai(invalid):
    from tax_benchmark.crewai_harness import run_crewai

    responses = iter([invalid, json.dumps({"action": "final", "answer": ANSWER})])
    prompts = []

    async def complete(messages):
        prompts.append(deepcopy(messages))
        return next(responses)

    async def tool(action):
        pytest.fail("Malformed output must not invoke a tool")

    result = await run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=2, complete=complete, tool=tool, available_tools=TOOLS,
    )
    assert json.loads(result) == ANSWER
    assert len(prompts) == 2
    assert "Invalid" in json.dumps(prompts[1])


async def test_invalid_output_cannot_exceed_host_model_call_cap():
    from tax_benchmark.crewai_harness import run_crewai

    calls = []

    async def complete(messages):
        calls.append(messages)
        if len(calls) > 2:
            pytest.fail("CrewAI exceeded its model call cap")
        return "not JSON"

    async def tool(action):
        pytest.fail("Malformed output must not invoke a tool")

    with pytest.raises(ValueError, match="2-turn"):
        await run_crewai(
            system_prompt="Return one JSON action per turn.", question=QUESTION,
            max_steps=2, complete=complete, tool=tool, available_tools=TOOLS,
        )
    assert len(calls) == 2


@pytest.mark.parametrize(
    "failure", [BudgetError("shared cap reached"), asyncio.CancelledError(), RuntimeError("provider rate limit")]
)
@pytest.mark.parametrize("boundary", ["model", "tool", "validation"])
async def test_callback_abort_is_preserved_without_extra_model_calls(failure, boundary):
    from tax_benchmark.crewai_harness import run_crewai

    model_calls, tool_calls = [], []

    async def complete(messages):
        model_calls.append(messages)
        if boundary == "model":
            raise failure
        if boundary == "validation":
            return json.dumps({"action": "final", "answer": ANSWER})
        return '{"action":"case_facts"}'

    async def tool(action):
        tool_calls.append(action)
        raise failure

    async def validate_final(answer):
        if boundary == "validation":
            raise failure

    with pytest.raises(type(failure)) as stopped:
        await run_crewai(
            system_prompt="Return one JSON action per turn.", question=QUESTION,
            max_steps=4, complete=complete, tool=tool, available_tools=TOOLS,
            validate_final=validate_final,
        )
    assert stopped.value is failure
    assert len(model_calls) == 1
    assert len(tool_calls) == (boundary == "tool")


async def test_search_arguments_reach_host_without_rewriting():
    from tax_benchmark.crewai_harness import run_crewai

    actions = []
    responses = iter([
        {"action": "search_sources", "query": "§ 43b {certificate}"},
        {"action": "final", "answer": ANSWER},
    ])

    async def complete(messages):
        return json.dumps(next(responses))

    async def tool(action):
        actions.append(action)
        return {"sources": [{"id": "law", "text": "Search evidence."}]}

    await run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=2, complete=complete, tool=tool, available_tools=TOOLS,
    )
    assert actions == [{"action": "search_sources", "query": "§ 43b {certificate}"}]


async def test_cancelling_harness_stops_pending_callback_and_future_work():
    from tax_benchmark.crewai_harness import run_crewai

    started, stopped = asyncio.Event(), asyncio.Event()
    calls = []

    async def complete(messages):
        calls.append(messages)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def tool(action):
        pytest.fail("Cancellation must stop tools")

    task = asyncio.create_task(run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=4, complete=complete, tool=tool, available_tools=TOOLS,
    ))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(stopped.wait(), 2)
    assert len(calls) == 1


async def test_missing_optional_dependency_fails_before_host_callback(monkeypatch):
    import builtins

    from tax_benchmark.crewai_harness import run_crewai

    original_import = builtins.__import__

    def without_crewai(name, *args, **kwargs):
        if name == "crewai":
            raise ImportError("optional package absent")
        return original_import(name, *args, **kwargs)

    async def forbidden(*args):
        pytest.fail("Missing CrewAI must not reach host model or tool callbacks")

    monkeypatch.setattr(builtins, "__import__", without_crewai)
    with pytest.raises(RuntimeError, match="orchestration dependency extra"):
        await run_crewai(
            system_prompt="Return one JSON action per turn.", question=QUESTION,
            max_steps=2, complete=forbidden, tool=forbidden, available_tools=TOOLS,
        )


async def test_framework_markers_inside_json_strings_preserve_tool_arguments_and_answer():
    from tax_benchmark.crewai_harness import run_crewai

    answer = {**ANSWER, "reasoning": "A quoted Final Answer: label is evidence text."}
    actions = []
    responses = iter([
        {"action": "search_sources", "query": "document titled Final Answer: withholding"},
        {"action": "final", "answer": answer},
    ])

    async def complete(messages):
        return json.dumps(next(responses))

    async def tool(action):
        actions.append(action)
        return {"sources": [{"id": "law", "text": "A Final Answer: label in evidence."}]}

    result = await run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=2, complete=complete, tool=tool, available_tools=TOOLS,
    )
    assert json.loads(result) == answer
    assert actions == [{"action": "search_sources", "query": "document titled Final Answer: withholding"}]


@pytest.mark.parametrize("invalid_answer", [
    {"status": "determined"},
    {**ANSWER, "total_withholding_cents": 27},
    ANSWER,
])
async def test_invalid_final_can_retrieve_evidence_and_repair_within_remaining_calls(invalid_answer):
    from tax_benchmark.crewai_harness import run_crewai

    prompts, actions, validated = [], [], []
    delivered_sources, delivered_evidence = set(), set()
    responses = iter([
        {"action": "final", "answer": invalid_answer},
        {"action": "case_facts"},
        {"action": "read_source", "source_id": "law"},
        {"action": "final", "answer": ANSWER},
    ])

    async def complete(messages):
        prompts.append(deepcopy(messages))
        return json.dumps(next(responses))

    async def tool(action):
        actions.append(action)
        if action["action"] == "case_facts":
            delivered_evidence.add("record")
            return {"documents": [{"id": "record", "text": "Synthetic payment evidence."}]}
        delivered_sources.add("law")
        return {"id": "law", "text": "Withholding source."}

    async def validate_final(answer):
        validated.append(deepcopy(answer))
        try:
            TaxAnswer.model_validate(answer)
        except ValidationError:
            return "Follow the structured tax answer schema and withholding arithmetic."
        if (set(answer["source_ids"]) - delivered_sources
                or set(answer["evidence_ids"]) - delivered_evidence):
            return "Retrieve the source and evidence IDs before citing them."
        return None

    result = await run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=6, complete=complete, tool=tool, available_tools=TOOLS,
        validate_final=validate_final,
    )
    assert json.loads(result) == ANSWER
    assert len(prompts) == 4
    assert actions == [{"action": "case_facts"}, {"action": "read_source", "source_id": "law"}]
    assert validated == [invalid_answer, ANSWER]
    assert any(message["content"] in (
        "Follow the structured tax answer schema and withholding arithmetic.",
        "Retrieve the source and evidence IDs before citing them.",
    ) for message in prompts[1])


async def test_bare_answer_requires_repair_to_explicit_final_action():
    from tax_benchmark.crewai_harness import run_crewai

    prompts, validated = [], []
    responses = iter([ANSWER, {"action": "final", "answer": ANSWER}])

    async def complete(messages):
        prompts.append(deepcopy(messages))
        return json.dumps(next(responses))

    async def tool(action):
        pytest.fail("A bare answer repair must not invoke a host tool")

    async def validate_final(answer):
        validated.append(answer)
        return None

    result = await run_crewai(
        system_prompt="Return one JSON action per turn.", question=QUESTION,
        max_steps=2, complete=complete, tool=tool, available_tools=TOOLS,
        validate_final=validate_final,
    )
    assert json.loads(result) == ANSWER
    assert len(prompts) == 2
    assert validated == [ANSWER]
    assert "Invalid structured action" in json.dumps(prompts[1])
