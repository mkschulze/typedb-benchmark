# Application API and Worker Contract

All endpoints use `/api`. JSON lists are returned directly, without a wrapper. Errors use `{"detail": "human-readable message"}`. No credential values are returned.

## Domain data

`data/cases.json` is a list of case objects; `data/sources.json` is a list of sources; `data/gold.json` maps case ID to an independently specified provisional expected answer/rubric. Gold is not supplied to any agent tool.

A case has `id`, `title`, `summary`, `category`, `split` (`development` or `evaluation`), `question`, `gross_amount_cents` (integer), `payment_date`, `knowledge_date`, `payer` and `recipient` objects (`id`, `name`, `country`, optional `legal_form`), `facts` (JSON object with explicit unknowns), `documents` (list of evidence objects with `id`, `title`, `text` and dates where applicable), `source_ids` (list of source IDs), and `review_status: "provisional"`.

A source has `id`, `title`, `url`, `locator`, `text` (a concise sourced passage/summary), `retrieved_at`, `sha256` and optional application/version dates. Legal summaries are labeled as summaries and linked to the preserved source.

A tax answer has `status` (`determined`, `needs_information`, `review_required`, `outside_scope`), `relief_eligibility` (`eligible`, `ineligible`, `undetermined`), `relief_route`, `withholding_tax_cents`, `solidarity_surcharge_cents`, `total_withholding_cents`, `net_payment_cents`, `refund_status`, `refund_amount_cents` (all amounts integer or null), `missing_facts` (list of strings), `source_ids`, `evidence_ids`, and `reasoning`. Extra supported fields are allowed. Unknown amounts are null.

Domain module interface:

- `load_cases() -> list[dict]`, `load_sources() -> list[dict]`, `load_gold() -> dict`.
- `reference_answer(case: dict) -> dict`: a deterministic, clearly labeled provisional reference walkthrough; no measured LLM metrics.
- `sql_answer(case: dict) -> dict`: SQL-control computation, matching the TypeDB function's supported semantics.
- `TypeDBStore()`: reads `TYPEDB_ADDRESS`, `TYPEDB_USERNAME`, `TYPEDB_PASSWORD`, `TYPEDB_DATABASE` from environment. `health() -> dict`, `seed(cases: list[dict]) -> None`, `context(case: dict) -> dict`, `evaluate(case: dict) -> dict`. Fail clearly if unavailable; never fall back to Python and call it TypeDB. Keep results JSON serializable.

## Read endpoints

- `GET /health`: `{"status":"ok", "typedb":{...}, "legal_review":"provisional"}`. Database health need not prevent browsing the app.
- `GET /cases`: all public case objects. `GET /cases/{id}`: one public case, 404 if absent.
- `GET /cases/{id}/reference`: `{"answer":<tax answer>, "kind":"reference", "review_status":"provisional"}`.
- `GET /sources`: source objects. `GET /models`: list of `{id, name, configured, provider}`.
- `GET /configurations`: `[{id, name, description}]`; IDs: `rag`, `typedb_context`, `typedb_functions`, `sql`.
- `GET /runs`: newest-first run objects. `GET /runs/{id}`: persisted run and trials.
- `GET /runs/{id}/export`: JSON download of manifest, states, trials, and aggregate metrics.

## Run endpoints

`POST /runs` body: `{case_ids: string[], model_ids: string[], configurations: string[], repetitions: integer=1, max_steps: integer=6}`. Validate every ID, nonempty unique selections, repetitions 1–5, max_steps 1–12, and at most 1,800 trials. Unconfigured models return 422 before enqueueing; missing selected TypeDB service returns 503 before execution. Returns a run immediately (HTTP 202).

`POST /runs/{id}/cancel` returns updated run. Stops new trials and requests cancellation; completed trials are preserved. Run states: `queued`, `running`, `completed`, `cancelled`, `interrupted`, `failed`.

A run has `id`, `status`, `created_at`, `updated_at`, `total_trials`, `completed_trials`, `request`, `manifest`, `trials`, `summary`. A trial has `id`, `case_id`, `model_id`, `configuration`, `repetition`, `status`, `answer` (nullable), `error` (nullable string), `passed` (boolean), `grading` (object), `metrics` (object), `trace` (list).

Trial metrics: `wall_time_ms`, `provider_time_ms`, `tool_time_ms`, `tool_calls`, `input_tokens`, `output_tokens`, `cached_tokens`, `reasoning_tokens`, `cost_usd`. Unknown usage/cost is null. Summary rows: `{model_id, configuration, trials, passed, failed, pass_rate, avg_wall_time_ms, avg_input_tokens, avg_output_tokens, avg_total_tokens}`. Expose numeric scores as provisional; do not fabricate benchmark data before runs.

Manifest records dataset/source/gold hashes, model IDs, public generation settings, prompts/tool definitions, dependency versions, limits, schedule seed, retrieval mode, and review status. No keys or other secrets.

## Local configuration

`MODELS_JSON` is a JSON array of backend model definitions: `[{"id":"local","name":"Local model","model":"model-name","base_url":"http://localhost:11434/v1","api_key_env":"LOCAL_MODEL_API_KEY","provider":"OpenAI-compatible"}]`. A missing key is allowed only for a loopback local endpoint; hosted endpoints must have the named environment variable configured. Default catalogue lists an unconfigured OpenAI-compatible model and explains setup; no live model calls run by default.

Optional `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY` enable dense retrieval, combined with lexical ranking. Without them, report `lexical` as retrieval mode and state that hybrid retrieval is not configured.

Frontend development uses Vite's `/api` proxy to FastAPI on port 8001. Production serves the frontend build from FastAPI. Default frontend dev port is 5173. Backend operational storage defaults to `.runtime/benchmark.sqlite3` and may be overridden with `BENCHMARK_DB_PATH`.
