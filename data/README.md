# Provisional tax fixtures

`cases.json` contains 10 development and 30 evaluation cases across six descriptive tax categories. Each case has a synthetic payment, dated facts and documents, an explicit requested relief route, and public legal source IDs. Counterfactual scenarios share a template group, and each complete group belongs to one split. All case facts remain accessible to every benchmark configuration.

The `split` field is authoritative. Case IDs are stable historical identifiers: a `dev-` or `eval-` prefix no longer indicates the split. Groups are assigned as follows:

| Split | Template group | Cases |
| --- | --- | ---: |
| Development | `domestic_math` | 5 |
| Development | `company_qualification` | 5 |
| Evaluation | `certificate_status` | 11 |
| Evaluation | `holding_period` | 4 |
| Evaluation | `anti_abuse` | 4 |
| Evaluation | `treaty_conditions` | 5 |
| Evaluation | `comprehensive_routes` | 1 |
| Evaluation | `dated_ownership` | 1 |
| Evaluation | `knowledge_cutoff` | 1 |
| Evaluation | `unsupported_scope` | 3 |

The evaluation split therefore does not contain five cases from every descriptive category. Keeping related certificate, qualification, holding-period and treaty counterfactuals together takes precedence over balancing category counts.

`gold.json` contains separately specified expected fields, including the exact requested `relief_route`, and legal/fact evidence requirements. `build_dataset.py` authors the scenario expectations explicitly; it does not call either calculation engine to create them. Engine agreement is a consistency check, not independent legal validation. A qualified independent review remains outstanding; all cases, gold and results are provisional.

`sources.json` registers the retrieved official statute, BZSt guidance, BMF treaty register and consolidated Germany–Netherlands treaty text. `raw/` preserves original response bytes and retrieval metadata. Every `raw_path` is relative to the repository root, including the generated implementation rules, so verification and regeneration work after relocating the checkout. SHA-256 covers those original bytes. Concise source summaries are explicitly labelled and do not replace the originals. The 2026 consolidated treaty (BGBl. 2026 II no. 102) includes the protocol applying from 1 January 2026. Retrieval date alone does not prove historical applicability; current statute application remains provisional.

Supported mechanical cases are ordinary cash dividends from a German GmbH to a Dutch corporation, paid in 2026 no later than 21 November. The engines distinguish substantive eligibility, an issued BZSt exemption available at payment, and conditional later refunds. A residence certificate or application is not an exemption certificate. Unknown inventory completeness is different from a complete inventory with no certificate.

EU relief uses explicit Annex 2 qualifications, direct participation including the statutory resolution-date rule, twelve uninterrupted months and explicit anti-abuse exception facts. A holding period completed after payment follows the later-refund route. Unresolved economic activity, ownership, AO §42 or conflicting-record judgments require review. Missing substance evidence is never automatically denial.

The treaty branch supports the ordinary 5% and 15% Article 10 caps, beneficial ownership and the 365-day period including payment. Under SolzG §5 the reduction applies to the surcharge first, so no surcharge is added above the combined treaty cap. Named-route refund figures assume remittance, timely application and the required tax certificate. Comprehensive relief including EStG §44a(9) and KStG §32 requires review.

Money is integer cents. Frozen gross values produce whole-cent 25% capital tax; fractional capital-tax cents are explicitly referred for review. Surcharge fractions are discarded separately under SolzG §4. The benchmark reports the payment-level withholding, not the payer's whole-euro aggregated remittance under EStG §44(1) sentence 6. TypeQL performs monetary arithmetic with decimal expressions and integer `floor`, SQLite with integer arithmetic.

Regenerate fixtures with `.venv/bin/python data/build_dataset.py`; then run the dataset verifier and reseed TypeDB. This changes the frozen dataset hash and must precede scored comparisons.
