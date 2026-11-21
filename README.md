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

The app uses port 8001; TypeDB uses local ports 1730 (gRPC) and 8002 (HTTP). Compose persists TypeDB in a named volume and runs/budget in the host `.runtime/` directory shared with `dev.sh`. The database credentials in `.env.example` are local development defaults.

For frontend development:

```bash
# Terminal 1, after the database has been started and seeded:
uv run tax-benchmark serve

# Terminal 2:
npm --prefix frontend run dev
```

Vite serves http://localhost:5173 and proxies `/api` to FastAPI on port 8001.

## Connect models

The reference walkthrough works without an API key. Add any of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `OPENROUTER_API_KEY` to the ignored local `.env`, then recreate the app (`docker compose up -d --force-recreate app`). Never put credentials in `.env.example`. The default `config/models.json` supplies explicit Claude, OpenAI and OpenRouter model IDs, dated prices and protocol settings. `config/model-sources.json` records their verification sources. `MODELS_JSON` can override the catalogue. Only model names and readiness reach the browser.

Claude uses the native Messages API; OpenAI and OpenRouter use Chat Completions. All use the same JSON-action protocol and output cap. Generation settings are recorded per model, including omission of sampling parameters when unsupported. Other compatible endpoints can be configured, but compatibility is only established after testing that endpoint. Each run allows 1–5 repetitions, 1–12 model turns per trial, at most 1,800 trials, and one active worker. Cancellation prevents new work after the current request is recorded.

One **€30 total experiment allowance** is shared by every provider, every run and optional embeddings. Atomic SQLite reservations happen before network requests and persist across restarts. The guard uses verified prices, conservative token bounds, a recorded USD/EUR conversion and a 1.3 safety margin. Unknown or failed-response charges retain the entire reservation. Complete reported usage releases the unused part; a charge exceeding its reservation permanently blocks further calls. The API and interface show allocated, reserved and remaining amounts. These are conservative application estimates, not provider invoices. Other applications or copies using separate databases are outside this ledger. Do not delete the run database/volume to reset spending.

Live calls require nonnegative input/output prices verified within 14 days. Missing or stale prices stop paid work. Cached reads, cache writes and reasoning counts remain separate. Verified cache-write ceilings cover unknown retention durations (OpenAI Standard: $5/MTok; Claude Sonnet: $4/MTok). A known write count without applicable pricing keeps its full reservation. OpenAI explicitly requests the Standard/default service tier; long-context requests without applicable prices stay unpriced. `cost_usd`/`estimated_cost_usd` are catalogue estimates; `provider_reported_cost_usd` preserves actual returned charge metadata. Settlement uses the greater known cost. Catalogue-based USD costs are estimates; the OpenRouter entry deliberately uses the higher timed rates. The allowance cannot be increased via an environment variable.

Optional `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`, `EMBEDDING_INPUT_PRICE_PER_MILLION` and `EMBEDDING_PRICE_DATE` enable budgeted hybrid BM25 + dense retrieval with reciprocal-rank fusion. Otherwise the manifest explicitly says `lexical`. Source summaries are the retrieval units. Source curation, database loading and embedding/index preparation are separate setup work; embedding calls still consume the same €30 allowance.

## Agent harnesses and language

The DE/EN header switch defaults to German and remembers the browser selection. Interface labels, synthetic case displays, source summaries and deterministic reference explanations are translated for presentation. Original evidence bodies, model reasoning, record identifiers and raw exports remain available in their original form. Language selection never changes benchmark prompts, cases or grading.

Choose **Direct agent** or **CrewAI** separately from the four data/tool approaches. CrewAI1.15.44 uses a real single Agent/Task/Crew, with memory, delegation, tool caching, planning and framework retries disabled. Its JSON-action bridge routes every model/tool call through the same host limits, evidence tracking and EUR30 ledger. Final-answer validation and bounded repair are shared. Actual provider messages, effective settings and framework version are recorded. Provider reasoning effort currently stays at its default; output is capped at2048 tokens per call in the recorded pilot.

`./dev.sh` and the Docker image install the optional orchestration dependency. For a manual installation use `uv sync --extra orchestration`. Without it the API exposes CrewAI as unavailable, with no direct-agent fallback carrying a CrewAI label.

A provider request has an absolute90-second deadline in addition to transport timeouts. Restart marks unfinished jobs interrupted. Explicit `POST /api/runs/{id}/resume` verifies the frozen inputs, preserves prior attempts, records an unresolved in-flight attempt as an execution failure with unknown usage and a retained reservation, then schedules only unattempted matrix entries. It never silently replays paid calls. `request_key` makes an identical run-creation retry idempotent; changing its payload returns409.

The finite follow-up coordinator is started with `.venv/bin/python -m tax_benchmark.workflow --plan /absolute/path/plan.json`. It waits for the approved direct run and all other queued/running work to finish, verifies the approved image and frozen inputs, then submits the keyed CrewAI pilot. Its state and audit paths are specified in that plan. Setting `enabled` to false stops the follow-up without cancelling the current user run; cancelling the direct run in the UI also prevents the follow-up. Budget exhaustion or interrupted jobs are preserved, without automatic replay.

The current local sequence is the user's360-trial direct batch followed by a48-trial CrewAI pilot, within the same EUR30 allowance. The independently saved48-trial direct pilot is available under `results/`; it is exploratory and uses cases previously involved in output-contract validation. Its paired within-model results show mixed efficiency gains, not a universal token-saving claim.

## Legal and experimental scope

The corpus contains 10 development and 30 held-out synthetic cases. Public case records and source summaries are separate from `data/gold.json`. Related counterfactuals share actual template groups, and those groups do not cross the development/evaluation boundary. Use the explicit split metadata; stable legacy case ID prefixes do not determine the split. Benchmark selection defaults to the evaluation cases. Presentation labels and outcome hints are excluded from model-facing facts.

The implemented core is ordinary 2026 German GmbH dividends to Dutch corporate recipients, with mechanical §43b conditions and the §50c distinction between withholding at payment and a conditional refund. Cases exercise participation and holding periods, issued certificates and their coverage/dates, missing evidence, and explicit review/scope outcomes. Treaty material and other relief routes are available as sources; unsupported or judgment-dependent treaty/comprehensive-relief requests receive `review_required`. Questions limited to §43b state that limitation. The result is not a complete German tax-advice engine.

The TypeDB configuration executes real TypeQL functions. It fails explicitly if the database is unavailable; it never substitutes a Python calculation and calls it TypeDB. The SQL control exposes equivalent supported decision logic. TypeDB context alone reads facts and evidence through TypeQL without computed tax outcomes. Its normalized model-visible case payload currently matches the source-retrieval arm, making this a backend parity control; it does not independently test a richer ontology representation. A benefit over retrieval establishes a contribution from that system configuration; it does not establish that the same logic cannot be implemented in SQL.

Every run records dataset/source/gold hashes, prompts, limits, dependency and model identifiers, settings, deterministic scheduling, raw model/tool traces, errors, and provider-reported token counts. A strict pass requires the requested relief route and source/document text actually delivered during that trial. Invalid answers and failed attempts remain in the scoring denominator, while incorrect answers, execution errors, and cancelled attempts are displayed separately. Cached and reasoning tokens remain separate, and reasoning tokens are not added twice. Budget-stopped incomplete trials are preserved as checkpoints and excluded from accuracy comparisons. Interrupted jobs are not automatically replayed after restart. A browser refresh can reopen saved runs from Benchmark → Run history. Exports contain paired pass-rate differences with template-cluster bootstrap intervals when at least two matched clusters are available; this small dataset is a pilot, not a universal performance claim.

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
