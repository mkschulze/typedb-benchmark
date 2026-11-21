"""CrewAI orchestration with all model and evidence access owned by the host."""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from concurrent.futures import Future
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

HARNESS_SETTINGS = {
    "framework": "crewai",
    "agent_count": 1,
    "process": "sequential",
    "allow_delegation": False,
    "memory": False,
    "cache": False,
    "planning": False,
    "max_retry_limit": 0,
    "respect_context_window": False,
    "use_better_compaction": False,
    "tracing": False,
    "protocol": "Host JSON actions translated to CrewAI ReAct; unchanged system prompt plus framework tool history",
}


class _AbortCrew(BaseException):
    """Bypass framework retries and restore the original host failure outside CrewAI."""


class _HostBridge:
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.failure: BaseException | None = None
        self.pending: Future | None = None

    def stop(self, failure):
        if self.failure is None:
            self.failure = failure
        raise _AbortCrew() from None

    def call(self, callback, *args):
        if self.failure is not None:
            raise _AbortCrew() from None

        async def invoke():
            try:
                return await callback(*args)
            except BaseException as failure:
                self.failure = failure
                raise

        self.pending = asyncio.run_coroutine_threadsafe(invoke(), self.loop)
        try:
            return self.pending.result()
        except BaseException:
            raise _AbortCrew() from None
        finally:
            self.pending = None


class _NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _SearchArguments(_NoArguments):
    query: str = Field(strict=True, min_length=1)


class _ReadArguments(_NoArguments):
    source_id: str = Field(strict=True, min_length=1)


def _never_cache(*_args):
    return False


def _react_json(value):
    # CrewAI searches the whole response for this marker, including quoted JSON strings.
    return json.dumps(value, ensure_ascii=False).replace("Final Answer:", "Final Answer\\u003a")


async def run_crewai(
    *,
    system_prompt: str,
    question: dict,
    max_steps: int,
    complete: Callable[[list[dict]], Awaitable[str]],
    tool: Callable[[dict], Awaitable[dict]],
    event: Callable[[dict], None] | None = None,
    available_tools: set[str] | None = None,
    validate_final: Callable[[dict], Awaitable[str | None]] | None = None,
) -> str:
    """Return final answer JSON; host callbacks retain usage, budget and cancellation control."""
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps must be a positive integer")
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["OTEL_SDK_DISABLED"] = "true"
    os.environ["CREWAI_TRACING_ENABLED"] = "false"
    # CrewAI imports load_dotenv itself; configuration belongs to the host.
    previous_dotenv_flag = os.environ.get("PYTHON_DOTENV_DISABLED")
    os.environ["PYTHON_DOTENV_DISABLED"] = "true"
    try:
        from crewai import Agent, BaseLLM, Crew, Process, Task
        from crewai.tools import BaseTool
    except ImportError as failure:
        raise RuntimeError("CrewAI orchestration requires the orchestration dependency extra") from failure
    finally:
        if previous_dotenv_flag is None:
            os.environ.pop("PYTHON_DOTENV_DISABLED", None)
        else:
            os.environ["PYTHON_DOTENV_DISABLED"] = previous_dotenv_flag

    bridge = _HostBridge()

    class CallbackLLM(BaseLLM):
        _calls: int = PrivateAttr(default=0)
        _repair: str | None = PrivateAttr(default=None)

        def _invalid(self, feedback=None):
            self._repair = feedback or "Invalid structured action. Return one JSON object following the system action and answer schema."
            # CrewAI treats unparsed prose as final; its invalid-tool route retains the bounded retry loop.
            return "Action: invalid_json_action\nAction Input: {}"

        def _final(self, answer):
            if validate_final is not None:
                feedback = bridge.call(validate_final, answer)
                if feedback is not None:
                    return self._invalid(feedback)
            return "Final Answer: " + _react_json(answer)

        def call(self, messages, tools=None, callbacks=None, available_functions=None, **_kwargs):
            if self._calls >= max_steps:
                bridge.stop(ValueError(f"No valid final answer within the {max_steps}-turn budget"))
            self._calls += 1
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            outgoing = [{"role": "system", "content": system_prompt}, *deepcopy(messages)]
            if self._repair:
                outgoing.append({"role": "user", "content": self._repair})
                self._repair = None
            raw = bridge.call(complete, outgoing)
            try:
                action = json.loads(raw)
            except (ValueError, TypeError):
                return self._invalid()
            if not isinstance(action, dict):
                return self._invalid()
            if action.get("action") == "final" and isinstance(action.get("answer"), dict):
                return self._final(action["answer"])
            if isinstance(action.get("action"), str) and action["action"] in definitions:
                arguments = {key: value for key, value in action.items() if key != "action"}
                return f"Action: {action['action']}\nAction Input: {_react_json(arguments)}"
            return self._invalid()

        def supports_function_calling(self):
            return False

        def supports_stop_words(self):
            return False

    class CallbackTool(BaseTool):
        def _run(self, **arguments):
            result = bridge.call(tool, {"action": self.name, **arguments})
            return json.dumps(result, ensure_ascii=False)

    definitions = {
        "case_facts": ("Read this payment's dated facts, parties and supporting documents.", _NoArguments),
        "search_sources": ("Retrieve up to five source passages for query.", _SearchArguments),
        "read_source": ("Read one source passage by source_id.", _ReadArguments),
        "evaluate_payment": ("Run the curated payment decision and return its supporting text.", _NoArguments),
    }
    enabled = {"case_facts", "search_sources", "read_source"} if available_tools is None else available_tools
    if enabled - definitions.keys():
        raise ValueError("Unknown CrewAI tool")
    registered = [
        CallbackTool(name=name, description=description, args_schema=schema, cache_function=_never_cache)
        for name, (description, schema) in definitions.items() if name in enabled
    ]
    llm = CallbackLLM(model="benchmark-callback", provider="benchmark", temperature=0)
    agent = Agent(
        role="Tax benchmark assessor",
        goal="Assess the supplied synthetic payment using permitted evidence tools.",
        backstory="Use the host's answer schema and supplied evidence.",
        llm=llm,
        tools=registered,
        allow_delegation=False,
        memory=False,
        cache=False,
        planning=False,
        max_retry_limit=0,
        max_iter=max_steps,
        respect_context_window=False,
        use_better_compaction=False,
        verbose=False,
        system_template=(
            "CrewAI single-agent benchmark task. Available tools: {tool_names}\n{tools}\n"
            "Return JSON actions as specified by the system prompt. "
            "Action/Observation lines in the history record previous framework activity."
        ),
        prompt_template="{input}",
    )
    task = Task(
        description=json.dumps(question, ensure_ascii=False),
        expected_output="The final tax answer JSON object required by the system prompt.",
        agent=agent,
    )
    crew = Crew(
        agents=[agent], tasks=[task], process=Process.sequential,
        memory=False, cache=False, planning=False, tracing=False, verbose=False, share_crew=False,
    )
    if event:
        event({"kind": "framework", **HARNESS_SETTINGS, "available_tools": sorted(enabled)})
    try:
        output = await asyncio.to_thread(crew.kickoff)
    except _AbortCrew:
        if bridge.failure is not None:
            raise bridge.failure
        raise RuntimeError("CrewAI callback execution stopped") from None
    except asyncio.CancelledError as failure:
        bridge.failure = failure
        if bridge.pending is not None:
            bridge.pending.cancel()
        raise
    final = json.loads(output.raw)
    if isinstance(final, dict) and final.get("action") == "final":
        final = final.get("answer")
    if not isinstance(final, dict):
        raise ValueError("CrewAI did not return a final answer object")
    return json.dumps(final, ensure_ascii=False)
