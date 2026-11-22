# CrewAI Comparison Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent adapter, financial accounting and frontend work; root integrates and verifies.

**Goal:** Complete the direct three-model matrix, then execute the same four approaches through real CrewAI orchestration under the existing shared EUR30 cap.

**Architecture:** Add a run-level `harness` axis (`direct`, `crewai`) while preserving four data/tool configurations. A single CrewAI Agent/Task/Crew uses a custom BaseLLM bridge and the existing paid-call/tool callbacks; every model request remains budgeted, counted and traced. The direct loop and CrewAI share answer validation, evidence tracking and scoring.

**Tech Stack:** Existing FastAPI/React/TypeDB plus pinned CrewAI1.15.44 optional `orchestration` dependency.

**Spec:** User approved direct testing first, then CrewAI orchestration on2026-11-21; original domain design remains authoritative.

## Global Constraints

- One EUR30 allowance across every provider, embedding and harness; no automatic reset.
- Same models, four cases, four approaches, source/gold hashes, output cap2048 and six paid calls per trial for both harnesses.
- Single CrewAI agent; memory, delegation, cache, planning and framework retries disabled. No default/manager/formatter/embedding LLM may bypass the paid-call bridge.
- Frame protocol prompts may differ; actual messages and effective settings must be recorded. Fresh state per trial.
- Keep earlier calibration and cancelled attempts separately traceable. Results remain exploratory after output-contract validation and provisional legal gold.

## Review Focus

- Framework internal retries/forced finalization must never cause an uncounted or unbudgeted request.
- Cancellation and shutdown must stop new calls; an in-flight response and usage remain recorded.
- TypeDB/RAG tool permissions and delivered-evidence scoring stay identical across harnesses.
- Missing optional dependency produces an explicit unavailable state, never a direct-run fallback labelled CrewAI.
- Cache-write counts use verified dated upper prices; unknown pricing keeps reservations. Retroactive reconciliation must preserve its source/provenance.

### Task1: Cache-write accounting (financial worker)

**Files:** providers.py, budget.py, new costs.py and focused tests; model catalogue/provenance.

- [x] Observe RED for mixed fresh/cache-read/cache-write pricing and reservation bound.
- [x] Add verified cache-write upper price, explicit OpenAI Standard tier, and fail-closed long-context handling.
- [x] Verify focused tests; root integrates common pricing and documented reconciliation of old unreported reservations.

### Task2: Real CrewAI adapter (adapter worker)

**Files:** new crewai_harness.py and test_crewai_harness.py.

**Interface:** `async run_crewai(*, system_prompt, question, max_steps, complete, tool, event=None, available_tools=None) -> str` final TaxAnswer JSON. `complete(messages)` and `tool(action)` are asynchronous guarded callbacks supplied by RunService.

- [x] Write and observe failing offline actual-CrewAI tests for tool+final execution, permissions and sticky fatal callback errors.
- [x] Implement BaseLLM JSON-action to ReAct bridge, real Agent/Task/Crew, fixed settings and disabled telemetry.
- [x] Verify no SDK/default model invocation occurs outside complete callback.

### Task3: Run integration (root)

**Files:** models.py, runner.py, api.py; dependency/lock/build/startup files; API/runner integration tests.

- [x] Add run request harness and `/api/harnesses` readiness, retaining legacy direct behavior.
- [x] Extract shared guarded model/tool callbacks and validation; dispatch real CrewAI using those callbacks.
- [x] Record effective harness/version/settings and actual model messages; prove cap/cancellation/error/evidence invariants offline.
- [x] Install optional dependency and include it in runnable Docker/dev startup; retain unavailable dependency path.

### Task4: Run controls (frontend worker)

**Files:** App.tsx/types.ts/styles.css/App.test.tsx only.

- [x] Add capability-aware harness selector and run labels; preserve old stored runs as direct.
- [x] Verify mocked payload/readiness tests and production build; inspect responsive rendering under existing Impeccable direction.

### Task5: Comparison and handoff (root + fresh reviewer)

- [x] Finish native OpenAI direct cohort; preserve all direct traces and hashes.
- [x] Review financial/adapter integration and resolve material findings before CrewAI spending.
- [x] Run development CrewAI smoke for all three models.
- [x] After the user-approved360-trial direct batch completes, run the48-trial CrewAI pilot within the remaining budget.
- [x] Save raw exports and derived results with calibration/effort/routing limitations; update stale no-live-run documentation.


## Later user steering and recovery

The user requested German translation and a language switch, then explicitly confirmed the360-trial direct batch should finish before the48-trial CrewAI follow-up. The DE-default DE/EN interface was hot-copied without restarting its active backend. A pre-existing stalled request left that batch at2/360; recovery added an absolute90-second provider deadline, archived its exact checkpoint, preserved the unresolved attempt as one execution error with its full reservation, and resumed only unattempted keys. It progressed beyond6/360 after recovery. Original model inputs and scoring stayed frozen.

The finite host coordinator waits for completion and an empty queue, checks approved image/input hashes, then creates its48-trial CrewAI run with a unique request key. SQLite uniqueness and explicit continuation prevent accidental paid replay. The EUR30 ledger is never reset. Independently audited cache-write reconciliation converted52 known Standard-tier reservations to conservative verified ceilings while preserving original manifests/trial metrics. Unknown HTTP-error fees remain fully reserved.
