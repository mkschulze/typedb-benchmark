# Provisional tax fixtures

`cases.json` contains 10 development and 30 evaluation cases, five evaluation cases per family. Each case has a synthetic payment, dated facts and documents, an explicit requested relief route, and public legal source IDs. Template groups are confined to one split. All case facts remain accessible to every benchmark configuration.

`gold.json` contains separately specified expected fields and legal/fact evidence requirements. `build_dataset.py` authors the scenario expectations explicitly; it does not call either calculation engine to create them. Engine agreement is a consistency check, not independent legal validation. A qualified independent review remains outstanding; all cases, gold and results are provisional.

`sources.json` registers the retrieved official statute, BZSt guidance, BMF treaty register and consolidated Germany–Netherlands treaty text. `raw/` preserves original response bytes and retrieval metadata. SHA-256 covers those original bytes. Concise source summaries are explicitly labelled and do not replace the originals. The 2026 consolidated treaty (BGBl. 2026 II no. 102) includes the protocol applying from 1 January 2026. Retrieval date alone does not prove historical applicability; current statute application remains provisional.

Supported mechanical cases are ordinary cash dividends from a German GmbH to a Dutch corporation, paid in 2026 no later than 21 November. The engines distinguish substantive eligibility, an issued BZSt exemption available at payment, and conditional later refunds. A residence certificate or application is not an exemption certificate. Unknown inventory completeness is different from a complete inventory with no certificate.

EU relief uses explicit Annex 2 qualifications, direct participation including the statutory resolution-date rule, twelve uninterrupted months and explicit anti-abuse exception facts. A holding period completed after payment follows the later-refund route. Unresolved economic activity, ownership, AO §42 or conflicting-record judgments require review. Missing substance evidence is never automatically denial.

The treaty branch supports the ordinary 5% and 15% Article 10 caps, beneficial ownership and the 365-day period including payment. Under SolzG §5 the reduction applies to the surcharge first, so no surcharge is added above the combined treaty cap. Named-route refund figures assume remittance, timely application and the required tax certificate. Comprehensive relief including EStG §44a(9) and KStG §32 requires review.

Money is integer cents. Frozen gross values produce whole-cent 25% capital tax; fractional capital-tax cents are explicitly referred for review. Surcharge fractions are discarded separately under SolzG §4. The benchmark reports the payment-level withholding, not the payer's whole-euro aggregated remittance under EStG §44(1) sentence 6. TypeQL performs monetary arithmetic with decimal expressions and integer `floor`, SQLite with integer arithmetic.

Regenerate fixtures with `.venv/bin/python data/build_dataset.py`; then run the dataset verifier and reseed TypeDB. This changes the frozen dataset hash and must precede scored comparisons.
