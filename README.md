# Tax Context Benchmark

A FastAPI + React application for demonstrating German dividend withholding and testing how structured context changes an LLM's answers. The first screen explains a synthetic German GmbH → Dutch corporate shareholder payment. A separate view runs the same model across source retrieval, TypeDB context, TypeDB with decision functions, and a SQL control.

All 40 cases and their expected answers are **provisional pending independent legal review**. The application ships with no invented accuracy, token, latency, or savings figures. A reference walkthrough is a deterministic worked example, not an LLM benchmark result.

## Run locally

Requirements: Docker with Compose, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ (Node 24 is used in the container build).

```bash
./dev.sh
```

Open **http://127.0.0.1:8001**. The script starts the dedicated TypeDB service, installs locked dependencies, verifies the source corpus, seeds TypeDB, builds React, and starts FastAPI. Port 8001 avoids the existing service on port 8000. Existing databases and containers are not modified.

Alternatively, run the complete application in containers:

```bash
docker compose up --build
```

The app uses port 8001; TypeDB uses local ports 1730 (gRPC) and 8002 (HTTP). Compose persists the benchmark database and recorded runs in named volumes. The database credentials in `.env.example` are local development defaults.

For frontend development:

```bash
# Terminal 1, after the database has been started and seeded:
uv run tax-benchmark serve

# Terminal 2:
npm --prefix frontend run dev
```

Vite serves http://localhost:5173 and proxies `/api` to FastAPI on port 8001.

## Connect models

The reference walkthrough works without an API key. Live comparisons require a configured endpoint and explicit model ID. No hosted key or local Ollama endpoint was detected during setup, so a real-model evaluation has not been executed.

Copy `.env.example` to `.env` and add your model catalogue and key. For an OpenAI-compatible provider:

```dotenv
MODELS_JSON='[{"id":"primary","name":"My model","model":"YOUR_MODEL_ID","base_url":"https://YOUR_PROVIDER/v1","api_key_env":"MODEL_API_KEY","provider":"OpenAI-compatible"}]'
MODEL_API_KEY=YOUR_KEY
```

For a local OpenAI-compatible endpoint such as Ollama, use a loopback base URL (`http://localhost:11434/v1`) and an installed model's exact ID. Local loopback endpoints do not require a key. When running the app inside Docker, the model service must be reachable from that container; `localhost` refers to the app container, not your host. Restart FastAPI after changing the model configuration. The browser receives model names and readiness only; keys stay on the backend.

The adapter uses chat completions with a common JSON-action protocol, temperature 0, and a per-turn output cap. Endpoints must support that request shape. Other provider protocols require an adapter; this version does not claim every LLM has been tested. Per-run limits are 1–5 repetitions, 1–12 model turns per trial, at most 1,800 trials, and one active local worker. The UI shows the planned trial count before starting. Cancellation prevents new trials; an already running provider request may finish and remains recorded.

Optional `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, and `EMBEDDING_API_KEY` enable hybrid BM25 + dense retrieval with reciprocal-rank fusion. Without them, the run manifest explicitly says `lexical`; it is not presented as a configured hybrid baseline. Source summaries are the retrieval units, with links to preserved original snapshots.

Optional dated model prices (`input_price_per_million`, `output_price_per_million`, `cached_input_price_per_million`, `price_date`) enable model-call cost calculation only when the necessary usage is reported. Unknown usage and cost remain null. Source curation, database loading, and embedding/index preparation are separate setup costs, not a claim of free preparation.

## Legal and experimental scope

The corpus contains 10 development and 30 held-out synthetic cases. Public case records and source summaries are separate from `data/gold.json`. Scenario template groups do not cross the development/evaluation boundary. Benchmark selection defaults to the evaluation cases.

The implemented core is ordinary 2026 German GmbH dividends to Dutch corporate recipients, with mechanical §43b conditions and the §50c distinction between withholding at payment and a conditional refund. Cases exercise participation and holding periods, issued certificates and their coverage/dates, missing evidence, and explicit review/scope outcomes. Treaty material and other relief routes are available as sources; unsupported or judgment-dependent treaty/comprehensive-relief requests receive `review_required`. Questions limited to §43b state that limitation. The result is not a complete German tax-advice engine.

The TypeDB configuration executes real TypeQL functions. It fails explicitly if the database is unavailable; it never substitutes a Python calculation and calls it TypeDB. The SQL control exposes equivalent supported decision logic. TypeDB context alone returns relationships and evidence without computed tax outcomes. A benefit over retrieval establishes a contribution from that system configuration; it does not establish that the same logic cannot be implemented in SQL.

Every run records dataset/source/gold hashes, prompts, limits, dependency and model identifiers, settings, deterministic scheduling, raw model/tool traces, errors, and provider-reported token counts. Invalid answers and failed attempts remain in the scoring denominator. Cached and reasoning tokens remain separate, and reasoning tokens are not added twice. Interrupted jobs are not automatically replayed after restart. Exports contain paired pass-rate differences with template-cluster bootstrap intervals when at least two matched clusters are available; this small dataset is a pilot, not a universal performance claim.

## Verify

```bash
uv run tax-benchmark verify
uv run pytest -q
RUN_TYPEDB_INTEGRATION=1 uv run pytest tests/test_typedb.py -q
typeql-check < typedb/schema.tql
typeql-check < typedb/functions.tql
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Source files, URLs, timestamps, and SHA-256 checksums are preserved under `data/`. `verify` checks those hashes, scenario split isolation, and reference/rubric consistency. It does not replace independent legal validation.

## Interface and design

The user-selected stack is FastAPI, React with TypeScript, Vite, and TypeDB 3.15.0. The interface uses Impeccable's Operate guidance: a case-first workspace, inline evidence, accessible controls, responsive layouts, and explicit empty/error states.

The requested design authority is https://design.deloitte.com/. That hostname could not be resolved from the build environment. The current brand direction uses [Deloitte's public brand guidance](https://www.deloitte.com/fr/fr/about/story/logo.html), including Open Sans and its green-centered identity. Exact conformance with the supplied design-system components/tokens remains unverified.

## Project layout

| Path | Responsibility |
| --- | --- |
| `backend/tax_benchmark/` | API, queue, model protocol, retrieval, grading, domain and database adapters |
| `frontend/` | React application and interaction tests |
| `data/` | Public synthetic cases, source snapshots, separate provisional gold |
| `typedb/` | Typed schema and reusable decision functions |
| `tests/` | Backend, domain, and real TypeDB integration checks |
| `docs/superpowers/` | Approved design and implementation plan |
| `.runtime/` | Local persisted runs; ignored by Git |

This version runs locally with synthetic data. Authentication, multi-tenancy, arbitrary client-document uploads, public hosting, and tax-filing integrations are outside its scope.
