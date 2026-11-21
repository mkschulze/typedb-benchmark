# Dividend Benchmark Implementation Plan

> **For agentic workers:** Use the approved design and execute each task with focused verification. Independent frontend and domain/database work may proceed in parallel after the API contract is fixed.

**Goal:** Ship a runnable FastAPI and React application for explaining German dividend withholding and comparing configurable LLMs with retrieval, TypeDB context, TypeDB functions, and a SQL control.

**Architecture:** FastAPI exposes a case catalogue and a persisted, bounded local run queue. A provider-neutral agent loop calls domain tools; TypeDB and SQL expose equivalent domain results. React leads with a synthetic dividend case and evidence, with a separate batch-results view.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, HTTPX, SQLite, TypeDB 3.x, React, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-11-21-german-dividend-benchmark-design.md`

## Global Constraints

- Preserve provisional legal-review status and distinguish reference walkthroughs from measured model runs.
- Keep keys server-side, gold outside model tools, and missing values distinct from false/zero.
- Use real TypeDB queries and functions; a missing server is an explicit unavailable state.
- The requested design authority is design.deloitte.com; conformance is unverified until its contents can be accessed. Use sourced public Deloitte brand guidance provisionally.
- No paid evaluation without configured model endpoints and explicit per-run limits.

## Review Focus

- Invalid model output and unavailable usage cannot become successful answers or zero-token measurements.
- Certificate scope, expiry, issue/knowledge dates, and unknown certificate inventories require different outcomes.
- Unknown IDs and oversized batches must fail validation before execution.
- Cancellation and restart must preserve completed work without silently repeating paid calls.
- Browser refresh, provider failure, and narrow screens must retain an understandable user flow.

## Files and ownership

- Root: `pyproject.toml`, `backend/tax_benchmark/{api,models,runner,providers,retrieval,storage}.py`, `tests/{test_api,test_runner,test_storage}.py`, root startup/Compose/README/config.
- Domain worker: `data/**`, `typedb/**`, `backend/tax_benchmark/domain.py`, `backend/tax_benchmark/typedb_store.py`, `backend/tax_benchmark/sql_control.py`, `tests/test_domain.py`, `tests/test_typedb.py`. Own source acquisition, provisional gold, TypeDB/SQL parity, and schema execution.
- Frontend worker: `frontend/**` and its focused tests. Own responsive React implementation against `docs/api-contract.md` and Impeccable direction brief.
- Final reviewer: read-only whole-application review after integration. Impeccable finish reviewer/documenter run after rendered evidence exists.

### Task 1: Fix contracts and test boundary

- [x] Write `docs/api-contract.md`, project configuration, and failing API/runner tests.
- [x] Run tests and observe missing implementation failures.
- [x] Initialize the greenfield Git repository on a feature branch; preserve the user's editor settings.

### Task 2: Build the source-grounded domain and databases

- [x] Read official current legal sources and the installed modeling/typeql skills.
- [x] Write failing tests for money, certificates, missing facts, and TypeDB/SQL parity.
- [x] Implement versioned cases, evidence, separate provisional gold, a SQL control, typed schema, and actual TypeDB functions.
- [x] Validate syntax and execute integration tests against a pinned server; record supported legal scope explicitly.

### Task 3: Build the run service

- [x] Write failing tests for unknown IDs, limits, provider failures, usage, grading, persistence, cancellation, and interrupted restart.
- [x] Implement source retrieval, an OpenAI-compatible provider adapter, the common agent loop, isolated tools, and strict gold scoring.
- [x] Implement FastAPI endpoints from the contract with structured errors and a bounded queue.
- [x] Run focused and full backend tests.

### Task 4: Build the demonstration and results frontend

- [x] Read PRODUCT.md and the Impeccable craft floor; record the user-pinned Deloitte world and case-first experience in a surface brief.
- [x] Implement case selection, facts/evidence, reference inspection, model comparison, batch controls, result details, errors, and export.
- [x] Keep measured metrics empty until a real run supplies them; label all reference figures and synthetic material.
- [x] Run TypeScript/build and focused interaction tests.

### Task 5: Integrate local startup and verify

- [x] Add `.env.example`, Dockerfiles/Compose, startup instructions, and a source/data verification command.
- [x] Verify the real API, TypeDB, and browser-facing application together.
- [x] Exercise desktop/mobile layouts and the case/run/evidence flow; fix observed failures.

### Task 6: Review and hand off

- [x] Run a fresh whole-application code review and fix material findings with regression evidence.
- [x] Run the Impeccable finish review and document the shipped design from the rendered implementation.
- [x] Record exact passing checks and remaining external dependencies; provide the local app URL and startup command.

## Execution notes

The user approved implementation of the design. Proceed in this session without another approval round. There is no existing Git repository, so initialize a feature branch in this workspace rather than moving the user's files to a new checkout. Exact model choices and access to the supplied design system remain external dependencies; they do not prevent building the local app.


### Added user-authorized provider and budget work

Claude native Messages, OpenAI Chat Completions and OpenRouter adapters are covered by mocked contract tests. A dated model catalogue configures explicit models. User authorized a EUR30 total allowance on2026-11-21; persistent reservations guard all chat/embedding calls across both launch paths. Fresh spending review identified ledger separation, provider-reported cost, empty billed responses, embedding checkpoints and rolling freshness; corrections and regressions were verified before any live spend. Optional embedding reported-charge settlement and null cache-write reporting were also corrected. Final checks:136 backend tests including TypeDB,12 frontend tests, production build, source verification and TypeQL syntax passed. No paid calls have occurred; local credentials remain an external prerequisite.
