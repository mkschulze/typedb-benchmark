# German Dividend Withholding Tax Benchmark

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

User-selected FastAPI backend and React frontend. TypeDB supplies the structured context and decision functions. The project has the upstream TypeDB modeling and TypeQL skills installed locally and globally, and `typeql-check` is available.

## Users

The first screen serves a client demonstration: lead with a dividend case and explain the comparison. Configuring and inspecting batch benchmark runs is a secondary workflow.

## Product Purpose

Recreate the experimental idea in the Databricks Genie Ontology benchmark for German dividend withholding tax. Measure whether access to structured context and explicit decision logic improves an LLM's answers, token use, and response time. Support different LLMs through a shared runner rather than tying the experiment to one provider.

## Operating Context

Synthetic German dividend payments to foreign corporate shareholders, supported by official legal sources. The demonstration must distinguish relief eligibility from the payer's withholding obligation at payment. Users compare approaches and inspect the sources behind answers.

## Capabilities and Constraints

- User-confirmed scope: Germany, withholding tax, dividends.
- User-confirmed interface: FastAPI, React, and the Impeccable skill.
- The user approved implementation of the design in `docs/superpowers/specs/2026-11-21-german-dividend-benchmark-design.md`.
- The user approved Claude, OpenAI and OpenRouter providers and a EUR30 total experiment limit. An explicit dated model catalogue and persistent shared budget guard are implemented; usable server-side keys are required for live evaluation.
- A48-trial direct exploratory pilot has been executed across Claude, OpenAI and OpenRouter. A user-started360-trial direct batch is followed by a48-trial CrewAI pilot under the same EUR30 allowance; broader performance claims remain unestablished.
- The user requested a German-default DE/EN interface; display translation preserves original benchmark inputs and evidence.

## Brand Commitments

The user requested Deloitte design and supplied https://design.deloitte.com/ as the design system. This is the requested visual authority. Its contents could not be retrieved in the current environment; precise component and token conformance remains unverified. Do not invent design-system rules or label a provisional implementation compliant with that system.

## Evidence on Hand

- Inspiration: https://www.databricks.com/blog/genie-genie-ontology-delivers-16-accuracy-less-half-tokens
- Legal source starting points: EStG §§ 43a, 43b, 44, 50c, and 50d; SolzG 1995; official BZSt guidance.
- Installed TypeDB skill provenance: `.agents/skills/typedb-skills-source.json`.
- The implemented FastAPI and React application includes a case-led reference walkthrough, comparison and batch-run controls, inline evidence, source provenance, and real TypeDB/SQL decision tools. The corpus contains 40 synthetic cases and 16 preserved source snapshots.
- Backend, TypeDB integration, and frontend interaction checks exercise the implementation. Real-model pilot exports are preserved under `results/`. Outcomes remain provisional; TypeDB context-only is a backend parity control and the SQL arm tests equivalent decision logic.

## Product Principles

- Show measured comparisons and traceable evidence.
- Preserve the difference between an unknown fact and a negative fact.
- Keep the experimental conditions comparable within each model.
- Make the first dividend example understandable before exposing batch controls.
