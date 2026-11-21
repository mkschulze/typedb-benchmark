# German Dividend Withholding Tax Benchmark Design

Status: approved for implementation by the user on 21 November 2026. Country, dividend scope, FastAPI, React, Impeccable, Deloitte design, and a client demonstration as the entry point are user-confirmed. The experiment, first treaty, dataset size, and implementation details below are builder decisions approved with this design; legal gold and exact Deloitte-system conformance still require their stated external validation.

## Purpose and success

Build a runnable web application that demonstrates and measures the effect of TypeDB context on LLM answers about German dividends paid to foreign corporate shareholders. The client can choose a synthetic payment, compare approaches using the same model, and inspect the evidence. A secondary benchmark view runs reproducible comparisons across configured models.

Success means a defensible, reproducible experiment and a working demonstration. An improvement is a hypothesis, not an acceptance condition. Report ties and regressions. The [Databricks example](https://www.databricks.com/blog/genie-genie-ontology-delivers-16-accuracy-less-half-tokens) inspires the evaluation, but its agent and harness comparison does not establish an expected effect size here.

## Approaches

| Approach | Tradeoff | Decision |
| --- | --- | --- |
| A prepared tax demonstration | Fast to present, but a selected example cannot establish an overall improvement | Use as the entry experience, with clearly identified synthetic cases |
| A controlled benchmark and demonstration | More dataset and grading work; separates contributions and can be reproduced | Recommended implementation |
| A general tax assistant | Broad legal and product scope; harder to establish ground truth or experimental control | Outside this version |

## Tax scope and source policy

First version: ordinary cash dividends from a German GmbH to foreign corporations. Propose the Netherlands as the first recipient jurisdiction so the same corpus can cover EU parent-company relief and one bilateral treaty. Other countries, individuals, funds, REITs, permanent-establishment attribution, liquidation distributions, restructurings, and tax filings are outside the first release. A case with an unsupported fact pattern must identify its scope limit rather than silently applying a simplified rule.

Use a source snapshot retrieved during implementation with a cutoff of 21 November 2026. Each source records its URL, retrieval timestamp, checksum, statutory/article locator, publication information when available, and separately verified application dates. A retrieval date does not establish that a provision applied to an earlier payment. Start with 2026 payments no later than the cutoff. Historical law changes require separate source versions and checked application dates; do not invent changes to make temporal tests harder.

The initial source register is:

| Source | Role |
| --- | --- |
| [EStG §43a](https://www.gesetze-im-internet.de/estg/__43a.html) | Domestic withholding rate and tax base |
| [EStG §43b](https://www.gesetze-im-internet.de/estg/__43b.html), its Annex 2, and the referenced EU provisions | Parent-company relief, company qualifications, direct participation, and holding period |
| [EStG §44](https://www.gesetze-im-internet.de/estg/__44.html) | Withholding time and payer responsibilities |
| [EStG §50c](https://www.gesetze-im-internet.de/estg/__50c.html) | Exemption certificates and refund procedure |
| [EStG §50d(3)](https://www.gesetze-im-internet.de/estg/__50d.html) | Relief restrictions and statutory exceptions |
| [SolzG 1995 §§3–5](https://www.gesetze-im-internet.de/solzg_1995/BJNR097500993.html) | Surcharge base, calculation, rounding, and treaty reduction treatment |
| [BZSt dividend relief guidance](https://online.portal.bzst.de/SharedDocs/Leistungsbeschreibung/DE/erstattung_abzugsteuer_kapitalertraege_50c_estg.html) | Administrative context and documentary requirements |
| [BMF Germany–Netherlands treaty register](https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Niederlande/2012-12-10-Niederlande-Abkommen-DBA.html) | Applicable treaty, protocols, and application dates |

Read and verify the relevant provisions before implementing any calculation. The treaty register reports a protocol applicable from 1 January 2026; the original 2012 text alone is insufficient as a source for 2026 cases. Exact treaty rates and conditions must come from the applicable official text, not this draft or a secondary rate table.

Keep separate outputs for substantive relief eligibility, the amount to withhold at the queried payment time, and the possible refund route. A short holding period does not automatically mean relief is permanently unavailable: §43b contains a later-completion refund provision. Likewise, a residence certificate is not a BZSt exemption certificate. Never compute treaty outcomes by automatically adding 5.5% to a quoted treaty rate; validate the treaty and surcharge treatment together.

Anti-abuse conclusions must follow the actual statutory conditions and exceptions. Missing substance evidence alone is not an automatic denial. V1 resolves clear, expressly modeled conditions and requests review for unresolved legal judgments. Generic relief claims and refund amounts must account for other relevant relief routes, including checking §44a(9) and KStG §32 before declaring a result exhaustive. Where a question is deliberately limited to a named route, state that limitation in the task and output.

## Experimental configurations

Use one common agent loop, question, output contract, source corpus, and budget for each model. Compare four configurations:

| Configuration | Available context | What the comparison can tell us |
| --- | --- | --- |
| Retrieval baseline | Search and read source passages; retrieve case records | Performance of a documented retrieval approach |
| TypeDB context | Same source access plus structured facts, relationships, and applicable source references; no tax decision functions | Contribution of the structured context interface |
| TypeDB with functions | Same access plus explicit, reusable tax decision functions with evidence references | Additional contribution of executable decision logic |
| SQL control | Same access and equivalent curated facts and decision logic exposed through the same domain tools as the full TypeDB configuration | Whether the observed benefit requires TypeDB or follows from structured knowledge and rule execution more generally |

The retrieval baseline uses a documented hybrid lexical and dense retrieval configuration, tuned on development cases only. All configurations can search the complete source corpus and read matching source text. Every curated fact and executable condition must be supported by material accessible to the baseline; publish the curated rule descriptions with the corpus. Gold decisions and grading criteria are not retrievable.

TypeDB context and full TypeDB share the same fact-retrieval tools; only the decision-function tool differs. The full TypeDB and SQL control tools use equivalent input and output schemas. Backend conformance fixtures check those two return the same semantic results. With equivalent outputs, accuracy and token parity is an expected legitimate result; backend-specific latency and implementation characteristics can still differ. Do not describe a full TypeDB versus RAG advantage as proof that SQL cannot do the same work.

Freeze prompts, tool schemas, retrieval settings, source and dataset hashes, server versions, model identifiers, generation settings, and per-run limits in each run manifest. Keep retries and repair attempts inside the recorded trace and budget. No live web browsing during scored runs. Each trial starts a fresh conversation.

## Cases and gold answers

Propose 10 development cases and 30 held-out evaluation cases, with six evaluation families of five cases each:

1. Domestic calculation and source selection.
2. EU parent-company qualifications, direct participation, and holding periods.
3. Relief at payment versus a possible later refund; certificate type, scope, and validity.
4. Treaty conditions, eligibility, and interaction with domestic relief routes.
5. Dated ownership and documentary changes, stale case records, and conflicting source versions.
6. Missing facts, unsupported scope, and anti-abuse questions requiring review.

Include simple lookups alongside complex cases. Freeze the full dataset before model comparisons. Split whole scenario templates and their counterfactual variants together so evaluation cases are not development cases with renamed companies. Match comparable case families across systems. Build the general fact and rule model without held-out expected answers; do not add payment-specific answers or hand-picked retrieval paths.

Each task has independently prepared expected structured fields, required legal/fact evidence, accepted clarification requests, and a review status. A separate reviewer or qualified domain expert must approve legal gold before presenting scores as a validated German tax benchmark. Implementation can run against provisional fixtures, but every such result and export is labeled provisional. A self-consistency check against the TypeDB function is not independent legal validation.

Use exact decimal money or integer cents, explicit rate units, and rule-specific rounding. Do not use binary floating-point arithmetic for money. Compare outcomes and amounts deterministically. Check citations against task evidence requirements and the source spans actually returned in the trace. Any model-based assessment is supplemental and separately identified.

## Demonstration flow

The landing screen is an application workspace led by a dividend example. Suggested wireframe, pending the accessible Deloitte design-system material:

```text
Tax Context Benchmark                  Demonstration | Benchmark | Sources

German dividend withholding tax
Choose a dividend case        Choose a model        Compare approaches

Payment and ownership facts  | Withholding and relief comparison
Dates and certificates       | Outcome, evidence, tokens, elapsed time
                             | Open one answer to inspect its sources
```

The client selects a curated case and one configured model, runs a comparison, and opens an answer's evidence. Evidence distinguishes case facts, legal sources, returned function results where applicable, and the final answer. Show the two dates that matter when relevant: the payment time and the information cutoff of the question. Do not expose hidden chain-of-thought; present tool traces, cited facts, and concise answer justifications.

The first example contrasts similar dividends with different certificate status, illustrating why an economic entitlement and a payer's immediate obligation can differ. Exact expected numbers are introduced only after the supporting rules and case assumptions have been checked.

Before execution, show an honest empty state. Synthetic fixtures may demonstrate facts and navigation but must never appear as measured model results. Saved real runs display their model, corpus version, and provisional/validated status. API errors, missing model configuration, unavailable TypeDB, interrupted jobs, no matching evidence, and partial comparisons each have explicit states. An offline deterministic walkthrough, if provided, is labeled as such and excluded from LLM scores.

The secondary benchmark view configures models, cases, repetitions, configurations, and limits; displays progress; and opens completed runs. Results include an accessible data table, simple comparative charts, and JSON export. The sources view shows the legal source register and versions. Native document links provide the complete source.

## Visual direction

The user has pinned Deloitte as the visual world and https://design.deloitte.com/ as the design-system reference. Use Impeccable in Operate mode for a precise, accessible application. Preserve that brand choice throughout any layout exploration. The supplied hostname currently does not resolve in this environment; no exact tokens or components have been extracted from it.

Public [Deloitte brand guidance](https://www.deloitte.com/fr/fr/about/story/logo.html) identifies Open Sans typography and a palette centered on Deloitte green. It is a possible provisional reference, not evidence of the supplied system's full component specification. Source any interim tokens explicitly and replace them with verified system tokens when accessible. Keep brand tokens separate from semantic status colors and chart-series identities. A green result is not synonymous with a passing result; text labels must carry state.

Use keyboard-operable controls, visible focus, semantic tables, adequate contrast, reduced-motion support, and responsive layouts. At narrow widths, stack fact and result regions while preserving access to every comparison. Inspect the rendered application on desktop and mobile widths. Final Impeccable review and documentation derive from the built interface; do not predeclare a final DESIGN.md from this draft.

## Architecture

Use a small monorepo: `backend/` for the FastAPI service and Python runner, `frontend/` for React with TypeScript and Vite, `data/` for source and fixture inputs, `typedb/` for schema/functions, and a Compose configuration for a pinned compatible TypeDB 3.x server. `PRODUCT.md` records user-confirmed product truth; this design records proposed implementation choices.

The browser talks only to FastAPI. Provider credentials and TypeDB access stay on the server. Normalize provider responses at a small adapter boundary so the evaluator and tool loop do not depend on a particular vendor. Start with configurable OpenAI-compatible endpoints and add other adapters only for models actually selected; do not claim an untested model is supported. Use provider-independent structured action parsing consistently within paired trials. Native tool calling may be used if held constant across configurations for that model.

FastAPI owns case/source reads, comparison and batch execution, grading, and result export. Store manifests, task states, and recorded results in SQLite; keep the SQL-control tables separate from operational tables and prohibit model access to gold/results. A single local execution worker and a bounded queue are sufficient initially. Persist state transitions, mark unfinished jobs interrupted after a process restart, and require an explicit rerun instead of replaying paid calls automatically. Use polling for progress rather than introducing a streaming infrastructure dependency.

Proposed API surface: `GET /api/cases`, `GET /api/cases/{id}`, `GET /api/sources`, `GET /api/models`, `POST /api/runs`, `GET /api/runs`, `GET /api/runs/{id}`, `POST /api/runs/{id}/cancel`, and `GET /api/runs/{id}/export`. A one-case comparison and a batch benchmark use the same run service. Validate model, case, and configuration identifiers server-side; return structured errors. Stop new work on cancellation and record any provider call that already completed.

Model keys come from server environment/configuration; never echo credentials in API responses, browser code, or traces. Default binding and CORS are for local development. Authentication, multi-tenancy, public hosting, arbitrary document upload, and external tax filing are outside this version.

## TypeDB model

Use named domain types and roles rather than an untyped universal node/edge store. Entities include corporations, jurisdictions, source versions/provisions, certificates, evidence documents, and payment records with stable IDs. Relations include dated shareholdings, dated residence assertions, dividend participation, certificate coverage, and evidence support. Attributes carry names, identifiers, dates, explicit status values, amounts in cents, and rates with named units. Use narrow cardinalities and ownership keys.

Store both when a fact is valid and when it is available to the task; absence of a row is not evidence that a fact is false. Negative evidence needs an explicit assertion or a declared complete inventory. A missing certificate record cannot stand for a verified statement that no qualifying certificate existed. Model percentage holdings on dated shareholding relations, not as permanent company attributes.

TypeDB 3.x uses explicitly called [functions](https://typedb.com/docs/reference/typedb-2-vs-3/diff/). Proposed reusable functions retrieve relevant ownership, select applicable sources, test resolved mechanical prerequisites, find certificate coverage, and compute supported withholding outcomes. Return evidence identifiers and unresolved prerequisites explicitly; do not assume TypeDB automatically supplies a legal proof or provenance graph. Keep monetary values integer-based at the data boundary and verify the selected server's decimal and date behavior. Validate TypeQL syntax with `typeql-check` and separately execute integration checks against the pinned server.

## Output and metrics

Each answer returns payment ID; payment and knowledge dates; relief route and eligibility status; withholding base, withholding tax, surcharge, total and net payment; refund route/status and amount when determinable; missing facts or review reason; and source/evidence identifiers. Unknown or unsupported numeric outputs are null with a reason, never zero by default. Distinguish no entitlement, insufficient evidence, outside scope, and execution failure.

The primary score is strict task pass: all required outcome fields and supporting evidence meet the task rubric. Report amount correctness, eligibility, procedural correctness, evidence support, and appropriate clarification separately so the aggregate can be audited. Empty, invalid, timed-out, and failed trials remain in the denominator, with error counts shown separately.

Record total elapsed time, provider-call latency, tool latency, tool counts, and provider-reported token usage across all calls and retries. Separate input, output, cached, and reasoning-token fields when supplied, without double-counting reasoning tokens already included in output. Missing usage remains unavailable rather than estimated as a measured value. Compare token totals primarily within each model because provider accounting differs.

Show monetary cost only when usage and a dated price configuration support it. Separate source curation, embeddings/index construction, and database load costs from query-time costs. Report warm/cold setup conditions. A client walkthrough never substitutes for aggregate evaluation.

The proposed full experiment is 30 held-out tasks × 3 models × 4 configurations × 5 repetitions = 1,800 trials; a trial can require multiple model calls. Run a small development smoke test first. Actual model IDs, credentials, and a live-call budget must be configured before paid evaluation. Randomize configuration order and schedule conservatively to reduce transient/provider effects. Estimate paired differences with confidence intervals clustered by scenario family/template, not by treating repeated calls as independent tax cases. The initial dataset supports a pilot, not a universal claim about German tax or all LLMs.

## Acceptance and handoff

1. One documented local startup path launches FastAPI, React, and a compatible TypeDB server, with clear configuration errors.
2. A client can select a dividend case, execute one configured model across the chosen configurations, and inspect comparable answers and supporting sources.
3. A second model runs through the same runner without changing tax or grading logic; a three-model evaluation remains a configurable target until the actual models are selected.
4. Missing or unresolved evidence yields explicit clarification/review outcomes. Temporal and certificate counterfactuals are verified by focused fixtures.
5. The retrieval baseline sees the supporting facts and rules. Gold is isolated. Full TypeDB and SQL-control semantic parity checks pass.
6. Run manifests and JSON exports reproduce dataset, sources, prompts, settings, results, and errors. No invented accuracy/savings appears in the interface.
7. Focused backend tests cover money/rounding, temporal selection, certificate distinctions, grading, and error states; TypeDB integration tests prove real queries and functions execute. Frontend verification covers the selection/run/evidence flow and desktop/mobile rendering.
8. A final Impeccable review records the rendered result and remaining design-system conformance limits; the shipped design system is documented from implementation.

Build in coherent slices after design approval: source-grounded case and gold contract; runnable FastAPI/React/TypeDB demonstration; retrieval and SQL controls plus model adapters; reproducible batch results and final visual verification. Exact dependencies, component boundaries, retrieval index implementation, and compatible server version are implementation-plan decisions. Broader tax coverage, infrastructure services, and deployment are separate work.

## Open dependencies

Implementation review adjustment: related certificate, holding-period, treaty, and other counterfactuals now share construction-template clusters. The corpus still has 10 development and 30 evaluation cases, but whole groups determine the split rather than forcing five evaluation rows per category. Category coverage describes the full corpus; `data/README.md` records the actual groups. Stable case IDs are preserved and split metadata is authoritative.

- Access to the supplied Deloitte design-system reference, an accessible equivalent, or an explicit choice to proceed from public brand guidance.
- Selected model endpoints/identifiers and credentials, with a live-run budget.
- Independent legal validation of gold answers before claiming a validated benchmark.

These dependencies do not prevent planning, preparing source material, or building a clearly labeled local demonstration once the design is approved.
