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

## Run a benchmark

Every trial sends real, paid model requests. At the current catalogue prices a trial costs about $0.06 with Claude, $0.035 with OpenAI and $0.006 with DeepSeek, so the full run below (450 trials) costs about $15. A 180-trial run took about 70 minutes, because one worker runs trials in sequence.

**In the browser:** open the **Benchmark** tab. Choose cases (the evaluation split is preselected; use **Filter dataset split** and **Select shown** to change it), models, approaches, the agent harness, repetitions and turns, then **Start benchmark**. Progress, scores and every trial's answer, evidence and tool log appear as the run goes; **Run history** reopens earlier runs, and **Export run JSON** downloads the raw export.

**Via the API**, to repeat the published comparison:

```bash
CASES=$(jq -c '[.[] | select(.split == "evaluation") | .id]' data/cases.json)
curl -s -X POST localhost:8001/api/runs -H 'content-type: application/json' -d "{
  \"case_ids\": $CASES,
  \"model_ids\": [\"claude-sonnet\", \"openai-sol\", \"openrouter-deepseek\"],
  \"configurations\": [\"rag\", \"typedb_context\", \"typedb_schema\", \"typedb_functions\", \"sql\"],
  \"repetitions\": 1, \"max_steps\": 6, \"harness\": \"direct\"
}" | jq -r .id                                                  # prints the run ID

curl -s localhost:8001/api/runs/RUN_ID | jq '{status, completed_trials, total_trials}'
curl -s -X POST localhost:8001/api/runs/RUN_ID/cancel           # stop after the current request
curl -s localhost:8001/api/runs/RUN_ID/export > export.json
uv run tax-benchmark summarize export.json > summary.json
```

`summarize` turns an export into the measured part of a `results/*.json` file: per model and approach the pass counts, `decision_fields_pass` (decision right, evidence ignored), errors by message, paired token and time differences against `rag`, and the bootstrap comparisons. The interpretation and limitations in the published files are written by hand. See `docs/api-contract.md` for all endpoints.

## Results so far

Each trial gives one model one case and one approach, with at most 6 turns. A trial passes only if the final answer gets **every** decision field and amount right (status, eligibility, relief route, withholding, surcharge, net payment, refund, missing facts) **and** cites the legal sources and case documents it actually retrieved in that trial. Errors, such as running out of turns or returning no answer, count as failures. Models: Claude Sonnet 5.5, OpenAI GPT-6.2 Sol and DeepSeek V4.1 Flash via OpenRouter, each on the same 30 held-out cases, one repetition.

**Passed out of 30:**

| Model | rag | context | schema | functions | sql |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude Sonnet | 0 | 1 | 2 | 25 | 24 |
| OpenAI | 16 | 16 | 17 | 19 | 18 |
| DeepSeek | 5 | 4 | 6 | 21 | 23 |

What this shows:

- **Giving the model the decision logic is what helps.** With `evaluate_payment` (TypeDB functions or SQL), Claude went from 0 to 25 and DeepSeek from 5 to 21–23. OpenAI already did reasonably without it and gained only 2–3 cases, which is within noise.
- **Structured facts or the schema alone do not help.** `context` gives the same facts as `rag`, read from TypeDB; `schema` adds the full TypeDB schema to the prompt. Both stay within 2 cases of `rag` for every model, and the schema costs 20–41% more tokens per trial.
- **Low `rag` scores are mostly about evidence, not arithmetic.** Claude got every decision field right in 12 of 30 `rag` trials but cited the required sources in none of them. It also ran out of turns in 9. The decision tool returns the supporting sources, which largely closes both gaps.
- **The decision tool is also cheaper and faster.** Compared with `rag`, functions used 13% fewer tokens for Claude, 56% fewer for OpenAI and 10% fewer for DeepSeek, and finished 25–39% faster.
- **This is not a TypeDB-only advantage.** SQL with the same curated logic scored about the same as TypeDB functions. The gain comes from having correct decision logic available as a tool.

Limits: 30 synthetic cases and one repetition, so differences of 1–2 cases are noise (OpenAI's `rag` scored 16 in one run and 15 in another). Some cases were used while tuning the answer format, and the expected answers still await legal review.

Sources: `rag`, `context`, `functions` and `sql` for Claude and OpenAI come from `results/2026-11-22-direct-matrix.json`. `schema` comes from `results/2026-11-22-schema-comparison.json`, whose own `rag` scores were 0 and 15. The DeepSeek row comes from `results/2026-11-22-deepseek-cap8192.json`, a re-run with an 8192-token output cap, because at 2048 its hidden reasoning used up the whole cap in 37% of trials and left no answer. Bootstrap confidence intervals are in the files.

## Scope

Ordinary 2026 dividends from a German GmbH to a Dutch corporation: §43b conditions, §50c withholding at payment versus later refund, participation and holding periods, exemption certificates, missing evidence and review/scope outcomes. Unsupported treaty or comprehensive-relief requests get `review_required`. This is not a tax-advice engine. The `split` field in `data/cases.json` is authoritative; template groups never cross splits.

Local, synthetic-data only: no authentication, uploads, public hosting or filing integrations.

## Verify

```bash
uv run tax-benchmark verify   # source hashes, split isolation, reference vs gold
uv run pytest -q
RUN_TYPEDB_INTEGRATION=1 uv run pytest tests/test_typedb.py -q
typeql-check < typedb/schema.tql && typeql-check < typedb/functions.tql
npm --prefix frontend test
npm --prefix frontend run build
```
