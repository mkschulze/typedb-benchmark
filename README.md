# Tax Context Benchmark

A FastAPI + React app that tests whether structured context (TypeDB) and explicit decision logic improve LLM answers on German dividend withholding tax. The first screen walks through a synthetic German GmbH → Dutch parent payment; the Benchmark view runs models across five approaches.

All 40 cases and expected answers are **provisional pending independent legal review**. Results are exploratory, not general accuracy or savings claims.

## Run

Requirements: Docker with Compose, [uv](https://docs.astral.sh/uv/), Node.js 22.12+.

```bash
./dev.sh                    # TypeDB, dependencies, verify, seed, build, serve
docker compose up --build   # or everything in containers
```

Open **http://127.0.0.1:8001**. TypeDB listens on 1730 (gRPC) and 8002 (HTTP). Runs and costs persist in `.runtime/`. For frontend work, run `uv run tax-benchmark serve` and `npm --prefix frontend run dev` (http://localhost:5173, proxies `/api`).

The interface is English by default, with a DE/EN switch. Translation affects only presentation, never prompts, cases or grading.

## Models and costs

The reference walkthrough needs no key. For live runs, add `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and/or `OPENROUTER_API_KEY` to `.env`, then `docker compose up -d --force-recreate app`. Models, prices and settings live in `config/models.json` (sources in `config/model-sources.json`; `MODELS_JSON` overrides). Claude uses the Messages API; OpenAI and OpenRouter use Chat Completions, all with the same JSON-action protocol. Output is capped at 2048 tokens per call, except 8192 for DeepSeek, whose hidden reasoning often used up 2048 tokens.

There is no spending limit. Every paid call records a conservative cost bound (verified prices, USD/EUR rate, 1.3 margin) before it is sent, and settles it afterwards; unknown charges keep the full bound. The header shows these totals, which are estimates, not provider invoices. Prices must be verified within 14 days, or paid calls stop.

Optional `EMBEDDING_*` variables (see `.env.example`) enable hybrid BM25 + dense retrieval; otherwise retrieval is lexical.

## Approaches and harnesses

| Approach | What the model gets |
| --- | --- |
| `rag` | Case facts, source search and source reading |
| `typedb_context` | The same facts read from TypeDB (parity control) |
| `typedb_schema` | `rag` plus the full `typedb/schema.tql` in the system prompt |
| `typedb_functions` | Plus `evaluate_payment` backed by TypeQL functions |
| `sql` | Plus `evaluate_payment` backed by equivalent SQL logic |

Each runs under the **Direct agent** or **CrewAI** (1.15.44, single agent; memory, delegation, caching and planning disabled; installed with `uv sync --extra orchestration`). Both share the same limits, evidence tracking and cost ledger.

Runs allow 1–5 repetitions, 1–12 turns per trial and up to 1,800 trials, with one worker. Each run freezes data/source/gold hashes, prompts and the schema. A restart marks unfinished runs interrupted; `POST /api/runs/{id}/resume` continues only unattempted trials and refuses if frozen inputs changed. `request_key` makes run creation idempotent.

## Results so far

Summaries are in `results/`. On 30 evaluation cases (strict pass out of 30):

| Model | rag | context | schema | functions | sql |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude Sonnet | 0 | 1 | 2 | 25 | 24 |
| OpenAI | 16 | 16 | 17 | 19 | 18 |
| DeepSeek (8192 cap) | 5 | 4 | 6 | 21 | 23 |

The schema and context columns come from separate runs whose `rag` baselines differed slightly; see the files. Curated decision logic (functions or SQL) is the only clear gain. Schema context showed no clear benefit and used 20–41% more tokens. This does not establish an exclusive TypeDB advantage: SQL with the same logic did about as well.

## Scope

Ordinary 2026 dividends from a German GmbH to a Dutch corporation: §43b conditions, §50c withholding at payment versus later refund, participation and holding periods, exemption certificates, missing evidence and review/scope outcomes. Unsupported treaty or comprehensive-relief requests get `review_required`. This is not a tax-advice engine. The `split` field in `data/cases.json` is authoritative; template groups never cross splits.

A strict pass requires every decision field, amount and evidence check, using only sources delivered during that trial. Failures and invalid answers stay in the denominator.

## Verify

```bash
uv run tax-benchmark verify   # source hashes, split isolation, reference vs gold
uv run pytest -q
RUN_TYPEDB_INTEGRATION=1 uv run pytest tests/test_typedb.py -q
typeql-check < typedb/schema.tql && typeql-check < typedb/functions.tql
npm --prefix frontend test
npm --prefix frontend run build
```

## Design

The requested design authority, https://design.deloitte.com/, could not be retrieved; the interface follows Deloitte's public brand guidance (Open Sans, green identity), and conformance remains unverified. See `DESIGN.md` and `PRODUCT.md`.

Local, synthetic-data only: no authentication, uploads, public hosting or filing integrations.
