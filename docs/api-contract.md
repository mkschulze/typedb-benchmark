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
- `GET /configurations`: `[{id, name, description}]`; IDs: `rag`, `typedb_context`, `typedb_schema`, `typedb_functions`, `sql`.
- `GET /runs`: newest-first run objects. `GET /runs/{id}`: persisted run and trials.
- `GET /runs/{id}/export`: JSON download of manifest, states, trials, and aggregate metrics.

## Run endpoints

`POST /runs` body: `{case_ids: string[], model_ids: string[], configurations: string[], repetitions: integer=1, max_steps: integer=6}`. Validate every ID, nonempty unique selections, repetitions 1–5, max_steps 1–12, and at most 1,800 trials. Unconfigured models return 422 before enqueueing; missing selected TypeDB service returns 503 before execution. Returns a run immediately (HTTP 202).

`POST /runs/{id}/cancel` returns updated run. Stops new trials and requests cancellation; completed trials are preserved. Run states: `queued`, `running`, `completed`, `cancelled`, `interrupted`, `failed`.

A run has `id`, `status`, `created_at`, `updated_at`, `total_trials`, `completed_trials`, `request`, `manifest`, `trials`, `summary`. It may have `error`, `active_trial`, and `cancellation_requested`. A running cancellation remains active until its in-flight response is recorded; no subsequent tool or model call starts. A trial has `id`, `case_id`, `model_id`, `configuration`, `repetition`, `status`, `answer` (nullable), `error` (nullable string), `passed` (boolean), `grading` (object), `metrics` (object), `trace` (list).

Trial metrics: `wall_time_ms`, `provider_time_ms`, `tool_time_ms`, `tool_calls`, `input_tokens`, `output_tokens`, `cached_tokens`, `reasoning_tokens`, `cost_usd`, and separate `embedding_usage`. Unknown usage/cost is null. Summary rows include `{model_id, configuration, trials, passed, failed, incorrect, errors, cancelled, pass_rate, avg_wall_time_ms, avg_input_tokens, avg_output_tokens, avg_total_tokens}`. `incorrect` means valid completed answers missing the rubric; `errors` means execution/protocol failures; `failed` is all nonpasses for compatibility. Expose numeric scores as provisional; do not fabricate benchmark data before runs.

Model-facing case context excludes presentation titles, summaries, split labels, and template groups. Full TypeDB and SQL tools normalize to equivalent decision content and attach the actual supporting source/document text. A strict pass requires the requested relief route and citations to passages/documents that the trial's tools actually returned; guessing corpus-wide IDs is insufficient.

Manifest records dataset/source/gold hashes, model IDs, public generation settings, prompts/tool definitions, dependency versions, limits, schedule seed, retrieval mode, and review status. No keys or other secrets.

## Local configuration

`MODELS_JSON` is a JSON array of backend model definitions: `[{"id":"local","name":"Local model","model":"model-name","base_url":"http://localhost:11434/v1","api_key_env":"LOCAL_MODEL_API_KEY","provider":"OpenAI-compatible"}]`. A missing key is allowed only for a loopback local endpoint; hosted endpoints must have the named environment variable configured. Default catalogue lists an unconfigured OpenAI-compatible model and explains setup; no live model calls run by default.

Optional `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY` enable dense retrieval, combined with lexical ranking. Without them, report `lexical` as retrieval mode and state that hybrid retrieval is not configured.

Frontend development uses Vite's `/api` proxy to FastAPI on port 8001. Production serves the frontend build from FastAPI. Default frontend dev port is 5173. Backend operational storage defaults to `.runtime/benchmark.sqlite3` and may be overridden with `BENCHMARK_DB_PATH`.


## Shared experiment budget

`GET /api/budget` returns `spent_eur`, `reserved_eur`, `committed_eur`, `usd_per_eur`, `safety_multiplier`, `pending_reservations`, and `unreported_reservations`. `spent_eur` includes the safety margin and is not an invoice total. There is no spending cap; the ledger records costs across all runs/providers/embeddings on the persisted run store. Calls reserve before dispatch; absent usage keeps the full bound. Prices older than 14 days fail closed. A budget stop (for example stale prices) yields run status `interrupted` and a readable `error`; an incomplete paid trial remains in `active_trial`, outside scored trials. Model manifests include `generation_settings`; budget reservations are correlated in traces.

Cost fields: trial `metrics.cost_usd` is retained as a catalogue estimate alias of `estimated_cost_usd`; `provider_reported_cost_usd` is null unless every response reported a valid charge. Unknown cache-write counts remain null. Each `embedding_events` entry persists its reservation before dispatch and updates reported usage/cost or failure, including setup errors.

`TaxAnswer.relief_route` is the canonical assessed route code, copied from `case_facts.facts.requested_route` or the decision result. Descriptive route wording belongs in `reasoning`. This contract is supplied equally to all four approaches.


## Harnesses, retries and explicit recovery

`GET /api/harnesses` returns `id`, `name`, `available`, `description` and optional version fields. `RunRequest.harness` is `direct` (default/legacy) or `crewai`; this is independent of the five configurations. A missing pinned CrewAI dependency returns503 before work. Manifests record framework settings, version and absolute provider deadline; `model_request` trace events preserve portable messages and removed framework metadata keys.

An optional `request_key` (1–100 letters/digits/`_.:-`) makes creation idempotent. The same canonical request returns its original run, including terminal states; a different body with that key returns409. SQLite enforces uniqueness. No replay occurs on a retry.

`POST /api/runs/{id}/resume` explicitly continues an interrupted run only after verifying its frozen case/source/gold/prompt inputs and configured services. An unresolved checkpoint is retained as a failed execution attempt with unknown aggregate usage and full fee reservation; the original checkpoint is copied into `continuations`. Existing trial keys are skipped. Cancellation/failed setup is not automatically resumed. `/api/health.worker.available` reports the local consumer's liveness.

Language is a frontend presentation preference. No locale field is sent to the benchmark runner or model provider.

`typedb_schema` supplies the structural `typedb/schema.tql` in the system message, with the same tools as `rag`/`typedb_context`; `evaluate_payment` stays unavailable. Runs selecting this approach include `manifest.schema_context` with `path`, exact `text`, UTF-8 `sha256` and the effective `system_prompt`. Explicit continuation also verifies that snapshot. Other configurations and historical manifests retain their existing semantics. Up to five configurations may be selected; the 1,800-trial cap is unchanged.
