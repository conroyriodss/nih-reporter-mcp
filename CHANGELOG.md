# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.14.8] - 2026-10-22

### Added
- `docs/evaluation.md` now has the four sections the deliverables specification requires. Section 3 is titled "Testing methodology" and opens with a summary of the test layers. Section 3.5 is "Performance metrics and behavioral cases" and adds a measured-figures table with an evidence tier on every row; the statement that no p50/p95 benchmark exists is kept. New section 9, "Security considerations", gathers the section 5.1 controls and SECURITY.md content with their boundaries. New section 10, "Lessons learned and recommendations", groups the section 7 repairs by goal. No existing section was renumbered.
- `docs/presentation/slides.md`: visible labels for the four required sections (slide 2 Problem statement, slide 3 Solution overview, slide 4 Demonstration of functionality, slide 5 Technical approach & key decisions) and an architecture line on slide 5.

### Changed
- Notebook, evaluation, manifest, slides and version stamps target v0.14.8. Server code is unchanged apart from the version string. CI remains 155 passed + 2 xfailed.

## [0.14.7] - 2026-10-22 (superseded by 0.14.8: evaluation and slides lacked the sections required by the deliverables specification)

### Fixed
- Notebook identity check: `parse_manifest_parent()` reads the RUN_MANIFEST §1 parent SHA from the single Submission tag row and its `**parent**` SHA cell, so punctuation in the surrounding prose no longer matters. At 0.14.6 the row's typographic apostrophes made the default identity path raise "parent row not found".
- EVAL_VERDICTS Claim 5 heading labels 18/18 as the originally claimed value.
- The A4 verdict in RUN_MANIFEST and `docs/demonstration_fixture/independent_total.md` now names the run it records, "VERIFIED at v0.13.0 (2026-10-19)", instead of HEAD. The A4 fixture-bundle row records the edited file (3,942 B).

### Changed
- Notebook, evaluation, manifest, slides and version stamps target v0.14.7. Server code is unchanged apart from the version string. CI remains 155 passed + 2 xfailed.

## [0.14.6] - 2026-10-21 (superseded by 0.14.7: notebook identity check failed on the manifest's typographic apostrophes)

### Fixed
- `docs/demo_script.md`: CI is 155 passed + 2 xfailed (was "38 passed + 2 xfailed"); correctness is 8/8 (was 5/5); the 10.1% figure is a basis difference.
- The CRISPR FY2023 10.1% and Alzheimer’s FY2023 16.5% figures are labeled as all_records vs whole_award basis differences in `docs/findings.md`, `docs/architecture.md`, `PROBLEM_STATEMENT.md` and `eval/README.md`. 166 of CRISPR’s 226 excluded subprojects are orphans, so the difference is not all duplication.
- `docs/agent_battery_test.md`: `is_exact` described as an internal aggregator property, not a returned field.
- `docs/findings.md` finding 14 cites 8 correctness tests (was 5); `eval/README.md` points to finding 14 (was #13).

### Changed
- `docs/presentation/slides.md` is the seven-slide deck with the orphan description (Team-reported P50HD096723 details) and no stale speaker-note about the evaluation command.
- Notebook, evaluation, manifest and version stamps target v0.14.6. Server code is unchanged apart from the version string. CI remains 155 passed + 2 xfailed.

## [0.14.5] - 2026-10-21 (superseded by 0.14.6: stale demo_script counts; 10.1%/16.5% labeled overstatement)

### Fixed
- RUN_MANIFEST A4 row for `docs/demonstration_fixture/independent_total.md` records the shipped bytes (3,926 B). The old row (3,971 B) predated the v0.14.2 SHA-citation edit to that file.
- `docs/evaluation.md` is the revised evaluation. Its CI table includes `tests/test_version_contract.py` and sums to 155 passed + 2 xfailed; the security count is 24 (was 21); the stale v0.14.0 change-log appendix is removed. The CRISPR sickle cell exclusion is described as an orphan (the keyword matched one P50HD096723 subproject, not the center), never as double-counting.
- `docs/presentation/slides.md`: the Alzheimer's demo table is labeled as award records (rank 3 is a component record of the rank-2 award). `is_exact` is no longer shown as a returned field; the tools return `complete`, `records_with_missing_amount` and `note`.
- RUN_MANIFEST: the v0.13.0 event-loop breakdown is Part B ×28 (sum 48, was 47).
- EVAL_VERDICTS Claim 6 heading labels 75 as the originally claimed value.

### Changed
- `notebooks/notebook-merged.ipynb` is the revised evaluation notebook. It unwraps FastMCP union-return results only for tools marked `x-fastmcp-wrap-result`, verifies the tag by the parent recorded in RUN_MANIFEST §1 (no hardcoded SHA), and labels its live checks as notebook-defined, distinct from the 17-case standalone smoke suite. Outputs cleared.
- Version 0.14.5. Server code is unchanged apart from the version string. CI remains 155 passed + 2 xfailed.

## [0.14.4] - 2026-10-21 (superseded by 0.14.5: stale manifest hash row; evaluation CI table summed to 154)

### Added
- `tests/test_version_contract.py` (runs in CI): serves the app in-process and asserts `/version` counts equal the live `list_*` lengths, with no literal counts. CI is now 155 pass + 2 xfail (203 collected).

### Changed
- CI count is 155 pass + 2 xfail everywhere (README, evaluation, slides, roadmap, robustness, EVAL_VERDICTS, RUN_MANIFEST); `ci.yml` and the README command include the new test.
- RUN_MANIFEST points to the v0.14.4 GitHub release notes for post-tag verification.

## [0.14.3] - 2026-10-20 (superseded by 0.14.4: no `/version` regression test; CI 154)

### Fixed
- `/version` computes `tools`, `prompts` and `resources` from the registered server on every request (`list_tools`/`list_prompts`/`list_resources`), so it can't disagree with the MCP list methods. v0.14.2 hardcoded `resources: 2`; the live count is 3.
- `test_prompt_contracts.py`: "13 tools" docstring and assert message corrected to 14.

### Removed
- `docs/run_manifest.md` (superseded 2026-10-18 manifest: 85 CI / 18 smoke). `docs/demonstration_fixture/RUN_MANIFEST.md` is now the only manifest; the old file is still in git history at v0.14.2 and earlier.

## [0.14.2] - 2026-10-20 (superseded by 0.14.3)

### Fixed
- Robustness counts now use one wording everywhere: 49 = 11 mocked (Part C, inside the 154 CI figure) + 38 server-dependent (32 stable + 6 pass-with-retry). v0.14.1 docs counted Part C twice.
- `docs/robustness.md`, `docs/architecture.md`, and the notebook updated to 14 tools / 3 resources; the notebook tool-count assertion was still `== 13`.
- Provenance corrections: model re-runs dated to v0.13.0; the STEP 4 behavioral traces and the A5 re-confirmation dated to v0.14.0.
- SHA-citation rule: document bodies cite tag names only; literal SHAs live only in `docs/demonstration_fixture/RUN_MANIFEST.md`.
- `docs/run_manifest.md` marked superseded.

## [0.14.1] - 2026-10-20 (superseded by 0.14.2)

### Changed
- CI now runs `tests/test_clinical_trials.py`: 154 pass + 2 xfail.
- `test_clinical_trials.py` uses `asyncio.run()`.
- Removed the dead `tools/clinical_trials_lookup.py` stub (the live tool is `tools/clinical_trials.py`).
- Part B document reconciliation (evaluation.md, slides.md, roadmap, eval/README).

## [0.14.0] - 2026-10-20 (superseded)

### Fixed
- Tool descriptions: deduped-grain routing and unsupported-capability abstention.
- Asyncio test harness; t5 smoke assertion (17/17).

## [0.11.0] - 2026-10-18

### Added
- **clinical_trials_lookup** tool (14th tool): find clinical trials linked to
  NIH grants or matching a condition via ClinicalTrials.gov v2 API.
  - Forward direction (NCT → grants): parses secondaryIdInfos + orgStudyIdInfo
  - Reverse direction (grant → NCTs): CT.gov query.id with project_num fallback
  - Evidence classification: `source_asserted` (structural grant declaration)
    vs `candidate` (condition search, no direct assertion)
  - NIH-vs-FDA disambiguation: filters on `type=="NIH"` — an R01-shaped ID
    from FDA appears as `type="OTHER_GRANT"`, never `type="NIH"`
  - Interventional/observational distinction via `studyType`
  - Registered-plan vs actual dates preserved as separate fields (TrialDatePair)
  - No dollar attribution to trials (prevents double-counting)
  - Boundary language on every response (link ≠ causation, absence ≠ no relationship)
- Hardened ClinicalTrials.gov v2 HTTP client (`utils_ctgov.py`):
  host allowlist, follow_redirects=False, trust_env=False, 20s timeout,
  5 MB response cap, 0.5s rate limit, 15-min TTL cache.
- 4 frozen test fixtures with decision ledger (`tests/fixtures/clinical_trials/`)
- 23 new unit tests (`test_clinical_trials.py`): grant extraction, trial parsing,
  fixture consistency, input validation, client robustness, counting discipline
- SECURITY.md updated: 4 upstream origins (was 3)

## [0.10.0] - 2026-10-15

### Fixed
- **Finding A: study_section_workload and investigator double-counting.**
  Both tools now route per-group / per-page summation through
  `aggregate_funding(funding_basis="whole_award")`, excluding subproject
  records and deduplicating by appl_id. Previously both summed
  `award_amount` raw, inflating totals for multi-component grants.
  `SubprojectId` and `ApplId` added to include_fields for both tools.
- **Finding B: evidence_bundle reproduction instructions and provenance.**
  `source_record_ids` now contains only the appl_ids that *contributed* to
  the dollar total (post-subproject-exclusion, post-dedup, non-null amounts
  only), not the pre-exclusion set. `reproduction_note` rewritten to
  describe the actual algorithm (exclude subprojects → dedupe → exclude
  null amounts → sum). Cap noted explicitly when contributing IDs exceed
  500.
- **Finding C: paginate_all completeness fooled by page-boundary dupes.**
  Now tracks distinct appl_ids during pagination; `complete` is computed as
  `len(distinct_ids) >= total` rather than `len(all_results) >= total`,
  which was inflated by page-boundary duplicate rows.
- **Finding D: conflicting-duplicate resolution was arbitrary.**
  `aggregate_funding` now distinguishes identical duplicates (collapsed
  silently) from conflicting duplicates (same appl_id, different
  award_amount/fiscal_year/subproject_id). Conflicts are still counted
  once (first-wins) but recorded in `AggResult.id_conflicts` and
  propagated to `Provenance.id_conflicts` for manual investigation.
- **Finding E: funding_trend discarded missing-amount information.**
  `records_with_missing_amount` propagated into each `YearFunding`. Note
  only says "All years aggregated exactly" when every year has zero missing
  amounts AND is complete.

### Added
- `AggResult.contributing_ids`: appl_ids that contributed to the dollar
  total (post-dedup, post-exclusion, non-null amount).
- `AggResult.id_conflicts`: appl_ids with conflicting duplicate data.
- `Provenance.id_conflicts`: surfaced to all provenance-bearing tools.
- `YearFunding.records_with_missing_amount` field.
- `SubprojectId` permanently in `INCLUDE_FIELDS` (shared field list).
- 7 new synthetic tests in `test_counting.py`: study_section whole_award,
  investigator whole_award, contributing_ids post-exclusion,
  page-boundary completeness, conflicting-duplicate flagging,
  identical-duplicate silence, missing-amount propagation.

### Changed
- `summarize_funding_by_topic` and `organization_funding_profile` provenance
  now uses `contributing_ids` (not pre-exclusion appl_ids) for
  `source_record_ids`, matching evidence_bundle's corrected behavior.
- **Scope-honest relabeling**: `check_investigator_overlap` docstring now
  describes it as "public funded-award screening" and notes it cannot see
  pending, non-NIH, or unpublished support. `study_section_workload`
  docstring now describes "funded-project distribution by study section"
  and notes it shows funded outcomes only, not review workload. Matching
  updates in `other_support_review` prompt, README, and roadmap.
- **Percentage convention standardized**: overstatement percentages now
  consistently use delta/corrected (e.g. CRISPR 10.1%, Alzheimer's 16.5%),
  not delta/naive (previously reported as 9.2% and 14.2%).
- **Finding 1** softened from "hard upstream ceiling" to "configured
  retrieval cap" — our paginator caps at 20×500=10,000; the upstream API
  behavior at high offsets was observed empirically but is not continuously
  verified by our test suite.
- **Finding 2** $921.5M now explicitly labeled "all_records basis" and
  noted as superseded by Finding 11's whole_award figure.
- Removed "unprompted" claim from demo Q4 description — the demo question
  explicitly asks for the comparison.
- **Smoke test assertions tightened**: t4 adds >$50M lower bound; t11
  uses strict `<` (not `<=`); t13 now asserts actual date_added descending
  order.

## [0.9.0] - 2026-10-15

### Added
- **In-process response cache** for `post_json` in `utils.py` — 15-minute
  TTL, keyed on SHA-256 hash of `(url, canonical-JSON-of-payload)`. Cache
  hits bypass the rate limiter entirely, reducing warm-path latency from
  4–6 seconds to ~0.02s (>100x speedup). No new dependencies (plain dict
  + timestamp eviction). Disabled via `NIH_MCP_CACHE_DISABLED=1` env var.
- `cache_stats()` and `clear_cache()` helpers in `utils.py` for
  observability and testing.
- Smoke test t18: cache correctness proof — verifies `whole_award` and
  `all_records` never collide in cache (same raw response, different
  aggregated totals) and that cold vs warm results are identical.
  Standalone suite now 17/17; notebook suite 18/18.
- Finding 12: documented cold-vs-warm latency and cache correctness
  properties in `docs/findings.md`.

### Changed
- `funding_trend_by_year` now fires per-year queries concurrently via
  `asyncio.gather`. The rate limiter still serialises upstream HTTP calls
  to ~1 req/sec on cache misses; on warm cache all years resolve in
  parallel (~20ms total). A 5-year trend drops from ~25s to <1s on warm.
- Cache key design: different `funding_basis` modes share the same cached
  raw API response (the HTTP payloads are identical); `aggregate_funding()`
  processes the cached data differently for each mode, preserving
  correctness without redundant cache entries.

## [0.8.0] - 2026-10-15

### Fixed
- **CRITICAL: Parent/subproject double-counting.** All aggregating tools
  (`summarize_funding_by_topic`, `organization_funding_profile`,
  `funding_trend_by_year`, `export_evidence_bundle`) now exclude subproject
  records by default, preventing the 10.1% overstatement found in CRISPR
  FY2023 ($921M → $837M, 10.1% overstatement). Per NIH RePORTER Data Elements PDF: parent award
  totals already include their subprojects' funding.
- Records with missing `award_amount` are now tracked separately
  (`records_with_missing_amount`) instead of being zeroed to $0.
- `appl_id` deduplication prevents page-boundary double-counting.

### Added
- `aggregate_funding()` helper in `utils.py` — the single, testable
  aggregation function used by all four funding tools.
- `funding_basis` parameter on all aggregating tools: `"whole_award"`
  (default, correct) or `"all_records"` (legacy, sums parent + children).
- `AggResult` data class carrying `total_award`, `record_count`,
  `records_with_missing_amount`, `deduped_count`, and
  `subproject_excluded_count`.
- New Provenance fields: `deduped_count`, `subproject_excluded_count`,
  `records_with_missing_amount`, `funding_basis`.
- New FundingSummary/OrgProfile fields: `funding_basis`, `deduped_count`,
  `subproject_excluded_count`, `records_with_missing_amount`.
- `COUNTING_UNIT_WHOLE` and `COUNTING_UNIT_ALL` constants replacing
  the ambiguous `COUNTING_UNIT` (retained as alias).
- `tests/test_counting.py`: 5 synthetic oracle tests + 2 xfail guards.
- `SubprojectId` and `ApplId` permanently in `AGG_FIELDS`.

### Changed
- t7 smoke test now verifies `whole_award < all_records` (proving dedup
  works), not just cross-tool total matching.
- t14 checks `funding_basis` and `subproject_excluded_count` instead of
  the old substring-in-counting-unit check.
- Finding 11 documents the 10.1% overstatement correction with full before/after figures.

## [0.7.0] - 2026-10-15

### Added
- `explain_health_topic` tool (13th tool): plain-language health-topic
  explanations from MedlinePlus (NLM Web Search API), in English or Spanish.
  Third upstream integration (wsearch.nlm.nih.gov) alongside RePORTER and
  NCBI E-utilities. Hardened client with SSRF protections, rate limiting,
  response size cap. No API key required.
- Smoke tests t16 (positive match with summary) and t17 (clean no-match
  handling). Standalone suite now 16/16; notebook suite 17/17.

## [0.6.0] - 2026-10-15

### Added
- **Provenance and counting-unit transparency**: `Provenance` model with
  `retrieved_at`, `query_criteria`, `total_matching`, `records_aggregated`,
  `complete`, `pages_fetched`, `source_api`, and `source_record_ids` (capped
  at 500). Makes any funding figure inspectable and reproducible.
- `counting_unit` field on `FundingSummary` and `OrgProfile` — explicitly
  documents the parent/subproject double-counting assumption in every
  response rather than hiding it.
- `include_provenance` parameter on `summarize_funding_by_topic` and
  `organization_funding_profile` (opt-in, default false, keeps normal
  responses lean).
- `export_evidence_bundle` tool (12th tool): runs the same aggregation as
  `summarize_funding_by_topic` with provenance always on, returning a bundle
  of summary + full provenance + counting-unit disclaimer + reproduction
  note. The "show me exactly which records summed to this total" tool.
- Smoke tests t14 and t15: provenance populated and counting-unit trap
  documented (t14), evidence bundle returns inspectable source record IDs
  (t15). Standalone suite now 14/14; notebook suite 15/15.
- `paginate_all` now returns `pages_fetched` and `appl_ids` (capped at 500)
  as additional return values, threading provenance data through the
  pagination layer.
- **Audience-specific prompt sets**: "one evidence base, two audiences"
  differentiator — no new data access, just composition and
  audience-appropriate framing. 5 new prompts (9 total):
  - `portfolio_brief` (program officer): reproducible cohort brief with
    IC/mechanism breakdown, evidence bundle, counting-unit caveat.
  - `other_support_review` (program officer): public funded-award screening
    for overlap candidates, with explicit boundary statement.
  - `investment_to_outputs` (program officer): project-to-publications
    dossier with source_reported labels and no funding-year attribution.
  - `explain_funding_landscape` (citizen scientist): plain-language funding
    overview with jargon definitions, geography clarification, and
    NIH-only scope disclaimer.
  - `follow_the_evidence` (citizen scientist): lay-reader narrative of a
    funded project distinguishing planned research from published findings.
- Per-test timeouts (90s) and **parallel test execution** via
  `asyncio.gather` in standalone smoke suite. Default mode now runs all 14
  tests concurrently (~60-90s wall-clock vs ~100s sequential). New
  `--sequential` flag preserves original serial behavior for debugging.

## [0.5.0] - 2026-10-15

### Added
- `research_landscape_summary` prompt (4th prompt): composes
  `summarize_funding_by_topic`, `funding_trend_by_year`, and
  `search_funded_projects` into a single analyst workflow for competitive
  research landscape assessment. Accepts `topic` and optional `years_back`
  (default 5), and instructs the calling agent to synthesize total
  investment, trend direction, top funded groups, and an explicit scope
  disclaimer (NIH-only, not the full research landscape).

### Changed
- Smoke test suite now supports `--quick` mode: runs 5 single-call tests
  (t3, t5, t6, t10, t13) in ~15 seconds for fast iteration during
  development, vs the full 12-test suite (~90 seconds). The notebook suite
  always runs all 13 tests.

## [0.4.0] - 2026-10-15

### Added
- `search_recent_awards` tool (11th tool): returns the most recently added
  NIH/HHS award records sorted by `date_added` (the date RePORTER's database
  was updated, not the award notice date — this distinction is documented in
  the tool's note field). Supports optional topic, state, and agency filters
  with a configurable limit (1–100, default 25). Verified that `sort_field:
  "date_added"` is accepted by the live API and that `date_added` returns an
  ISO datetime string and `is_new` returns a boolean.
- Smoke test t13: validates `search_recent_awards` returns results and
  respects the limit parameter. Standalone suite now 12/12; notebook suite
  13/13.

## [0.3.0] - 2026-10-15

### Added
- `study_section_workload` tool (10th tool): summarizes NIH funding outcomes
  grouped by scientific review study section — the peer-review panel that
  evaluated each application. Useful for SROs and program staff assessing
  review workload, funding concentration, or which study sections handle a
  given research area. Aggregates via full pagination and groups client-side
  by `full_study_section` (RePORTER's native field), returning per-section
  project counts, total award amounts, and which ICs funded through each
  section. Handles projects with no study section on record (intramural,
  contract mechanisms) by excluding them from the breakdown with an explicit
  count in the note.
- Smoke test t12: validates `study_section_workload` end-to-end — confirms
  at least one section group is returned and that per-section project counts
  reconcile with the total (section_sum ≤ total_projects). Standalone suite
  now 11/11; notebook suite 12/12.
- API field verification: confirmed live `full_study_section` response shape
  (`srg_code`, `srg_flex`, `sra_designator_code`, `sra_flex_code`,
  `group_code`, `name`) diverges from docs in two places — `group` is
  actually `group_code`, and `name` is the composite code string (e.g.
  `"ZRG1-MOSS-R(02)"`) not a human-readable name.

## [0.2.0] - 2026-10-15

### Added
- `check_investigator_overlap` tool (9th tool): surfaces an investigator's
  currently active NIH/HHS awards for program-officer duplication/overlap
  review (NIH "Other Support"). Supports explicit project exclusion
  (`exclude_project_num`) so the application under review is omitted,
  first-name disambiguation to reduce false positives on common surnames,
  and fiscal-year scoping. Returns flagged awards with overlap reasons and
  a clear disclaimer that results are candidates for human review, not
  actual duplication determinations.
- Smoke tests t10 and t11: end-to-end validation of
  `check_investigator_overlap` (structure + exclusion logic). Standalone
  suite now 10/10; notebook suite 11/11.

## [0.1.0] - 2026-10-15

### Added
- Initial release: 8 tools (before v0.2.0 addition), 3 prompts, 2 resources, custom HTTP routes.
- Template-compliant project layout (`src/nih_reporter_mcp/`).
- `get_publication_details` tool: resolves PubMed IDs into full citations
  via NCBI E-utilities esummary endpoint.
- SSRF hardening on all outbound HTTP clients (`follow_redirects=False`,
  `trust_env=False`, 10 MB response-size cap).
- Input-size guards: fiscal_years capped at 20, agencies/org_names at 20.
- Stub files for Tier 2 roadmap items: `clinical_trials_lookup.py`,
  `usaspending_comparison.py` (not registered; documented placeholders).
- Custom HTTP routes: `/health` (liveness probe) and `/version` (capability report).
- MCP prompts: `funding_overview`, `institution_report`, `compare_rcdc_vs_freetext`.
- MCP resources: `nih-reporter://spending-categories`, `nih-reporter://server-info`.
- `deploy/databricks/app.yaml` for Databricks Apps deployment.
- 9-assertion smoke test suite in the companion notebook.

### Fixed

#### `funding_trend_by_year` silently ignored `spending_category` parameter
- **Date**: 2026-10-14
- **Symptom**: Asking for year-over-year trends using an official RCDC
  spending category (e.g. "Cancer") returned all-zero funding amounts.
  The LLM would fall back to a topic-string workaround, which matched a
  much larger (and differently scoped) set of projects.
- **Root cause**: The `funding_trend_by_year` tool signature only accepted
  `topic` (required, positional). There was no `spending_category` parameter,
  so RCDC category IDs could not be passed to the upstream criteria builder.
  The LLM was forced to embed the category name as free text, which hit a
  completely different API code path.
- **Fix**: Added optional `spending_category` parameter (name or numeric ID)
  alongside optional `topic`; made `start_year` and `end_year` the required
  positional args. Added validation requiring at least one of
  `topic`/`spending_category`.
- **Regression test**: Smoke test t8 — calls `funding_trend_by_year` with
  `spending_category="Cancer"` and asserts every year has nonzero
  `project_count` and `total_award_amount_usd`.

#### 403 error leaked raw httpx traceback to the LLM
- **Date**: 2026-10-14
- **Symptom**: When a user's search text resembled SQL injection (e.g.
  `cancer" OR "1"="1`), RePORTER returned HTTP 403. The server re-raised
  this as a raw `httpx.HTTPStatusError` whose traceback included internal
  module paths and stack frames, leaking implementation details to the LLM.
- **Root cause**: The 403 status code was not handled explicitly; it fell
  through to the generic `resp.raise_for_status()` path, which raised an
  httpx exception with the full response body and stack.
- **Fix**: Added explicit 403 handling in `post_json` that raises a clean
  `ValueError` with a user-facing message ("RePORTER blocked this request
  (403), likely because the search text resembled a malicious pattern").
  No internal paths or stack frames are exposed.
- **Regression test**: Smoke test t6 — sends SQL-injection-style text,
  asserts the error message contains "403" and does NOT contain "httpx".
