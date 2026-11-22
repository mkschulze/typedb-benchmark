# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A FastAPI + React benchmark that measures whether structured context (TypeDB) and explicit decision logic improve LLM answers on synthetic German dividend withholding-tax cases. Real model calls cost real money; one persistent ledger records costs (there is no spending limit). All cases, gold answers and results are **provisional pending independent legal review**; never present results as established accuracy or savings claims. `PRODUCT.md` holds product scope and user-approved decisions; `DESIGN.md` holds the provisional visual system (Impeccable skill).

## Commands

```bash
./dev.sh                                   # TypeDB via Compose, uv sync, verify, seed, build React, serve on :8001
docker compose up --build                  # full stack in containers (app :8001, TypeDB :1730 gRPC / :8002 HTTP)

uv run --extra orchestration pytest -q                                   # backend tests (CrewAI tests skip without the extra)
uv run --extra orchestration pytest -q tests/test_runner.py::test_name   # single test
RUN_TYPEDB_INTEGRATION=1 uv run pytest -q tests/test_typedb.py           # needs running, seeded TypeDB; mutates it
uv run ruff check backend tests

npm --prefix frontend test                 # vitest
npm --prefix frontend run build            # tsc -b && vite build (also the type check)
npm --prefix frontend run dev              # :5173, proxies /api to :8001

uv run tax-benchmark verify                # source checksums, split isolation, reference engine vs gold
uv run tax-benchmark seed                  # idempotent TypeDB seed
typeql-check < typedb/schema.tql           # also typedb/functions.tql
```

Deploying to the running container: `.env` is read only at container creation, and `config/`, `data/`, `typedb/` are baked into the image. After changing keys run `docker compose up -d --no-deps --force-recreate app`; after changing config/code also `docker compose build app` first. Do this only when `/api/runs` shows nothing queued/running (a restart marks unfinished jobs interrupted), and back up `.runtime/benchmark.sqlite3` with SQLite's backup API first. `.env` is guarded by a hook; read `.env.example` for variable names.

## Architecture

**Run pipeline.** `api.py` (`create_app`) → `RunService` in `runner.py`, which owns a single-worker queue. `enqueue` builds a frozen *manifest* (dataset/sources/gold SHA-256, model catalogue and generation settings, effective system prompt, schema text and hash, package versions). `resume` re-verifies that manifest and refuses if anything changed, so edits to prompts, `typedb/schema.tql`, `data/*.json` or `config/models.json` block resuming older runs by design. Each trial is (case × model × configuration × repetition), run by a *harness*: `direct` (JSON-action loop inside `RunService.trial`) or `crewai` (`crewai_harness.py`, a bridge that routes every model/tool call back through the same host loop, limits and budget). `harnesses.py` pins CrewAI to an exact version.

**Configurations** (`models.CONFIGURATIONS`) differ only in tools and context, dispatched in `RunService.tool` and `system_prompt`:
- `rag`: `case_facts` (raw case), `search_sources` (`retrieval.py`, BM25, optional embedding hybrid), `read_source`.
- `typedb_context`: same tools, but `case_facts` comes from TypeDB, normalized to the same model-visible facts as `rag` (a parity control).
- `typedb_schema`: like `rag` plus the full `typedb/schema.tql` in the system prompt.
- `typedb_functions` / `sql`: additionally `evaluate_payment`, backed by TypeDB server functions (`typedb/functions.tql` via `typedb_store.py`) or the SQLite control (`sql_control.py`).

Prior results depend on the existing prompts staying byte-for-byte identical (checked by review when `typedb_schema` was added, not by a test); add new behavior as a new configuration, not by changing an existing one.

**Three independent decision engines plus separately authored gold.** `domain.reference_answer` (Python), TypeDB functions and `sql_control.evaluate_sql` must agree; `data/build_dataset.py` authors `gold.json` by hand, without calling any engine. `verify` and the TypeDB integration test check engine agreement against gold, which is a consistency check, not legal validation. `runner.grade_answer` scores strictly: every decision field, amount and evidence check must pass, and execution failures count as failures.

**Providers and budget.** `providers.py` (`ChatProvider`): Claude uses the native Messages API; OpenAI and OpenRouter use Chat Completions, all speaking the same JSON-action protocol. `budget.py` atomically reserves a conservative bound in SQLite (verified prices ≤14 days old, ×1.3 margin, recorded USD/EUR) *before* each network call and settles afterwards; unknown charges keep the full reservation. There is no cap, but stale prices stop paid calls; never delete the run database, it holds the cost history. `storage.py` (`RunStore`) persists runs/trials/traces in `.runtime/benchmark.sqlite3`.

**Follow-up coordinator.** `workflow.py` is a finite CLI (`python -m tax_benchmark.workflow --plan plan.json`) that waits for an approved run to finish, verifies image and frozen inputs, then submits a keyed follow-up run.

**Frontend.** Single-page `frontend/src/App.tsx`; first screen is a case-led reference walkthrough, batch runs are secondary. English is the default language, DE via the switch (`i18n.tsx`, `locales/content.de.json`); translation is presentation-only and never changes prompts, cases or grading.

## Results and data conventions

- `results/*.json` are hand-curated derived summaries (rows, paired efficiency, bootstrap comparisons, frozen input hashes, interpretation and limitations) of completed runs; full raw exports (`/api/runs/{id}/export`) stay in the gitignored `.runtime/`. In those summaries, `decision_fields_pass` means every non-evidence check passed, and a check missing from a trial counts as failed.
- `data/raw/` holds original source bytes; `sources.json` SHA-256 values cover them. The `split` field is authoritative; `dev-`/`eval-` ID prefixes are historical. Template groups never cross splits.
- `request_key` makes run creation idempotent; reusing a key with a different payload returns 409.
