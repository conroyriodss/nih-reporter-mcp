# Roadmap

## Done

- **8 tools**: 7 RePORTER-native (search, exact-total summarization, year-over-year trends, org profiles, investigator portfolios, direct ID lookup, publication linking) + 1 cross-API (PubMed citation resolution via NCBI E-utilities)
- **3 prompts**: `funding_overview`, `institution_report`, `compare_rcdc_vs_freetext` — reusable prompt templates that guide an LLM through multi-step analyses
- **2 resources**: `nih-reporter://spending-categories` (browsable RCDC category lookup table), `nih-reporter://server-info` (version, constraints, upstream API metadata)
- **2 custom HTTP routes**: `/health` (liveness probe for load balancers / Databricks Apps) and `/version` (capability report with tool/prompt/resource counts)
- Full pagination for exact totals (not a single-page estimate)
- Official NIH spending-category support (38 curated categories by name, any category by numeric ID) alongside free-text search, exposed as a deliberate choice rather than one hidden method
- Exact-match-by-default organization lookup to prevent silent cross-institution conflation
- Client-side active/inactive filtering (upstream criterion confirmed unreliable when combined with fiscal-year filters — see `docs/findings.md` #6)
- SSRF hardening on all outbound HTTP clients (`follow_redirects=False`, `trust_env=False`, 10 MB response-size cap) — defense-in-depth matching the [official template's hardening bar](https://github.com/GSA-TTS/mcp-hackathon-template)
- Input-size guards: fiscal_years capped at 20 per call, agencies/org_names at 20 items
- 9-assertion automated eval suite against live data, with hard invariants and drift-tolerant thresholds correctly distinguished
- Measured, regression-guarded LLM agent tool-selection accuracy (100% across 8 held-out questions) and tool-call efficiency (mean 1.0 calls/question after a documented tool-description fix)
- Reasoning-vs-chat-completion model endpoint compatibility documented and handled

## Stubbed, not implemented (see `src/nih_reporter_mcp/tools/*.py` for placeholder files)

**`clinical_trials_lookup`** — query ClinicalTrials.gov's v2 API to connect a funded project to any registered clinical trials, closing the loop from "NIH funds this research" to "this is now recruiting patients" or "this trial produced these results." The strongest available service-delivery complement to this server's current oversight-leaning tool set. No API key required.

**`usaspending_comparison`** — query USAspending.gov, the federal government's cross-agency spending API, to compare NIH's investment in a topic against total federal spending on that topic across all agencies. Answers a genuinely distinct oversight question RePORTER alone cannot: "how does NIH's piece compare to the whole federal picture?" No API key required.

Both are deliberately left unregistered (not exposed as live tools) rather than half-implemented, so the active tool set remains fully tested rather than including unverified behavior.

## Considered, not pursued

- **ORCID-based investigator disambiguation** — would fix the "common surname" ambiguity in `investigator_portfolio` with a stable identity key instead of name matching, but RePORTER's own API does not expose a cross-referenceable person ID suitable for this without additional reconciliation work beyond hackathon scope.
- **Front-end chat UI** — a Databricks Apps (Streamlit/Gradio) wrapper around the existing agent loop was scoped but deprioritized in favor of hardening the eval suite and tool set, per hackathon judging criteria emphasizing technical depth and evidence of testing over UI polish. The existing Databricks notebook (`notebook-merged`) serves as the interactive demo artifact.
- **Full ~300-category RCDC coverage** — only ~38 commonly-queried categories are resolved by name; the full Appendix I list could be embedded but was judged lower-value than other hardening given most real queries cluster around a well-known subset of conditions.
