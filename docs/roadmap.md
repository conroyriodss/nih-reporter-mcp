# Roadmap

## Done

- **14 tools**: 9 RePORTER-native (search, exact-total summarization with opt-in provenance, year-over-year trends, org profiles with opt-in provenance, investigator portfolios, investigator overlap/duplication check, funded-project distribution by study section, recent awards tracking, direct ID lookup) + 1 cross-API (PubMed citation resolution via NCBI E-utilities) + 1 hybrid (publication linking) + 1 audit (evidence bundle export with full provenance, source record IDs, and reproduction note) + 1 consumer health (plain-language health-topic explanations from MedlinePlus in English/Spanish via NLM Web Search) + 1 clinical trials (ClinicalTrials.gov v2 API lookup connecting funded projects to registered trials)
- **9 prompts** across 3 audiences (general/analyst, program officer, citizen scientist): `funding_overview`, `institution_report`, `compare_rcdc_vs_freetext`, `research_landscape_summary`, `portfolio_brief`, `other_support_review` (public funded-award screening), `investment_to_outputs`, `explain_funding_landscape`, `follow_the_evidence` — reusable prompt templates that compose the same tools with audience-appropriate framing and boundary language
- **3 resources**: `nih-reporter://spending-categories` (browsable RCDC category lookup table), `nih-reporter://server-info` (version, constraints, upstream API metadata), `nih-reporter://response-guidelines` (behavioral guidelines for agent responses)
- **2 custom HTTP routes**: `/health` (liveness probe for load balancers / Databricks Apps) and `/version` (capability report with tool/prompt/resource counts)
- Full pagination for exact totals (not a single-page estimate)
- Official NIH spending-category support (38 curated categories by name, any category by numeric ID) alongside free-text search, exposed as a deliberate choice rather than one hidden method
- Exact-match-by-default organization lookup to prevent silent cross-institution conflation
- Client-side active/inactive filtering (upstream criterion confirmed unreliable when combined with fiscal-year filters — see `docs/findings.md` #6)
- SSRF hardening on all outbound HTTP clients (`follow_redirects=False`, `trust_env=False`, 10 MB response-size cap) — defense-in-depth matching the [official template's hardening bar](https://github.com/GSA-TTS/mcp-hackathon-template)
- Input-size guards: fiscal_years capped at 20 per call, agencies/org_names at 20 items
- Provenance and counting-unit transparency: every aggregating response includes a `counting_unit` field documenting the parent/subproject double-counting assumption; opt-in `Provenance` object with query criteria, source record IDs, and timing for full auditability
- Audience-specific prompt sets: 9 prompts across 3 audiences (general/analyst,
  program officer, citizen scientist) composing the same tools with different
  framing and boundary language
- 17-assertion standalone smoke suite against live data + t9 LLM agent-efficiency (notebook-only), with hard invariants and drift-tolerant thresholds correctly distinguished
- 8 correctness-against-ground-truth tests (`tests/test_correctness.py`) proving funding arithmetic matches independently hand-computed reference values to the dollar
- 203 pytest tests across 7 files: 155 pass + 2 xfail offline (CI), 8 live-integration pass, 38 server-robustness pass
- Measured, regression-guarded LLM agent tool-selection accuracy (100% across 8 held-out questions) and tool-call efficiency (mean 1.0 calls/question after a documented tool-description fix)
- Reasoning-vs-chat-completion model endpoint compatibility documented and handled

## Stubbed, not implemented

**`usaspending_comparison`** — query USAspending.gov, the federal government's cross-agency spending API, to compare NIH's investment in a topic against total federal spending on that topic across all agencies. Answers a genuinely distinct oversight question RePORTER alone cannot: "how does NIH's piece compare to the whole federal picture?" No API key required.

Deliberately left unregistered (not exposed as a live tool) rather than half-implemented, so the active tool set remains fully tested rather than including unverified behavior.

**`clinical_trials_lookup`** was promoted from stub to fully registered tool at v0.13.0. It queries ClinicalTrials.gov's v2 API via `utils_ctgov.py`, with 23 offline tests in `test_clinical_trials.py`.

## Considered, not pursued

- **ORCID-based investigator disambiguation** — would fix the "common surname" ambiguity in `investigator_portfolio` with a stable identity key instead of name matching, but RePORTER's own API does not expose a cross-referenceable person ID suitable for this without additional reconciliation work beyond hackathon scope.
- **Front-end chat UI** — a Databricks Apps (Streamlit/Gradio) wrapper around the existing agent loop was scoped but deprioritized in favor of hardening the eval suite and tool set, per hackathon judging criteria emphasizing technical depth and evidence of testing over UI polish. The existing Databricks notebook (`notebook-merged`) serves as the interactive demo artifact.
- **Full ~300-category RCDC coverage** — only ~38 commonly-queried categories are resolved by name; the full Appendix I list could be embedded but was judged lower-value than other hardening given most real queries cluster around a well-known subset of conditions.
