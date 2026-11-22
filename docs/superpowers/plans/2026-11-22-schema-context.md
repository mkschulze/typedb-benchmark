# Schema Context Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; one fresh review after implementation.

**Goal:** Supply the structural TypeDB schema to the LLM and measure its isolated effect.

**Architecture:** Add `typedb_schema` alongside the four existing configurations. Freeze its schema text at service creation, include it only in that arm's shared system prompt, and persist its exact provenance. Preserve historical prompts and all paid-call guards.

**Tech Stack:** Existing FastAPI/Pydantic, React/TypeScript and TypeDB; no dependencies.

**Spec:** `docs/superpowers/specs/2026-11-22-schema-context-design.md`

## Global Constraints

- Shared EUR30 total cap; no ledger reset, no interruption of the running CrewAI pilot.
- Same model-facing facts, sources, grading, six-call limit and output cap as baseline.
- Only `typedb/schema.tql`; no functions, gold answers or computed decisions in the schema arm.
- Keep the four existing approach IDs and their prompts unchanged.

## Review Focus

- New prompt must reach actual provider requests through both harnesses.
- Schema bytes must be included in reservations and measured tokens.
- A changed schema must block explicit continuation of schema runs.
- Five approaches must work in DE/EN and at mobile widths without changing legacy requests.

## Task: Schema context and comparison

- [x] Add failing focused tests for prompt delivery, tool restrictions, manifest snapshot, continuation and five-arm validation.
- [x] Implement `typedb_schema` in models.py and runner.py; keep decision tools unavailable.
- [x] Add DE/EN copy and fifth-approach presentation; verify selection payload and responsive rendering.
- [x] Run backend suite, frontend suite/build, lint, source verification and fresh scoped review.
- [x] Wait for the CrewAI pilot to finish; deploy only with no queued/running work.
- [x] Start the keyed 180-attempt paired direct comparison within the existing budget; preserve actual progress and results.

Verification: 293 backend tests passed (2 TypeDB mutation/integration tests deliberately skipped while the live pilot is active); 24 frontend tests passed; production build, lint and corpus verification passed. Fresh read-only review found no material issues and confirmed all four legacy prompts match the previous commit byte-for-byte for step limits 1–12. Headless browser checks at 1440px and 390px in DE/EN found no overflow or runtime errors; desktop/mobile German renders were visually inspected.

Live verification: CrewAI pilot 421770f9-ba10-43a0-9c02-2adc2ab3b867 completed48/48 before deployment. A verified SQLite backup was made from inside the app container while no jobs were active. The new image’s frozen case/source/gold/prompt/schema hashes matched the approved plan before enqueue. Schema run a48892eb-c03a-4230-81ee-35bf5200fce5 was accepted for180 trials; its first six actual Claude requests contained the complete schema and exactly the recorded effective system prompt. Shared EUR30 budget and three prior unknown-charge reservations were retained.

Result: the schema run completed 180/180 on 2026-11-22; its derived summary is `results/2026-11-22-schema-comparison.json` (raw export `.runtime/schema-180-export.json`). No clear schema benefit: paired differences +2/+2/−2 cases (Claude/OpenAI/DeepSeek), all 95% intervals include zero, and mean tokens rose 20–41%.
