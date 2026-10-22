# Findings

Documented, reproducible discoveries made while building and testing this server. Each was verified against either the official NIH RePORTER API documentation, a raw API call bypassing our tool layer, or a manual cross-check against reporter.nih.gov's search UI.

## 1. Our paginator retrieves at most 10,000 records per query

Our paginator is configured to fetch up to 20 pages × 500 records = 10,000 records. During development we observed that the upstream RePORTER API also rejects high offsets (returning empty results or errors at offset ≥ 15,000), suggesting an upstream ceiling, but our test suite only verifies our own configured cap — not the upstream limit directly. A broad query like "cancer" in FY2023 has 23,486 true matches but only 10,000 are retrievable through our paginator.

**Why it matters:** A naive implementation either silently truncates (reporting a wrong total as if it were complete) or crashes on the offset ceiling. Every aggregating tool here (`summarize_funding_by_topic`, `funding_trend_by_year`, `organization_funding_profile`) returns an explicit `complete: bool` flag and a `note` explaining the shortfall when the cap is hit, rather than hiding it.

**Verified:** `summarize_funding_by_topic(topic="cancer", fiscal_years=[2023])` → `total_matching_projects=23486, projects_aggregated=10000, complete=False`.

## 2. The 500-record MVP cap materially understated real totals

Before implementing full pagination, an early version capped aggregation at a single 500-record page. For "CRISPR gene editing" FY2023, this produced **$580M** from 500 records. Full pagination across all 1,739 matching records returned **$921.5M on the all_records basis** (since superseded by the whole_award corrected figure of $837M in Finding 11). The 500-record cap understated even the naive all_records total by 37% (= ($921.5M − $580M) / $921.5M), and understated the corrected whole_award total by 30.7% (= ($837M − $580M) / $837M). This motivated full pagination as a correctness requirement, not an optimization.

## 3. NIH's official RCDC spending categories diverge sharply from free-text keyword search

For "Long COVID" in FY2023:

| Method | Matching projects | Total award amount |
|---|---:|---:|
| Official RCDC category ("Long COVID", ID 5194) | 154 | $209,603,849 |
| Free-text search for "long covid" | 1,148 | $891,742,057 |

A 4.25x difference. The RCDC number aggregates projects currently tagged with a congressionally-mandated category in live RePORTER data (which updates continuously and may differ from NIH's frozen published annual RCDC totals); free-text search catches any project that merely mentions the term, including tangential references. Additionally, RCDC categories overlap — a project can appear in multiple categories — so summing across categories double-counts. Neither method is "wrong" — they answer different questions — but presenting one as if it were the only truth would mislead. `summarize_funding_by_topic` accepts either method explicitly (`topic` for free-text, `spending_category` for live RCDC-category aggregation) and both paths are available as distinct tool calls, so an agent (or a human) can compare them rather than being forced into one framing.

This same divergence held for Alzheimer's Disease (RCDC $9.36B vs. free-text $12.07B over FY2022–2024) and is a structural property of the data, not a quirk of one topic.

## 4. Organization name matching is substring-based upstream, and silently combines institutions

Searching `org_names: ["Boston University"]` (RePORTER's fuzzy match) returns results for four distinct institutions: Boston University (Charles River Campus), Boston University Medical Campus, Tufts University Boston, and University of Massachusetts Boston. A tool that reported a single combined total under "Boston University" would be wrong by conflating unrelated institutions.

**Fix:** `organization_funding_profile` defaults to `exact_match=True` using RePORTER's `org_names_exact_match` criterion. An exact match on a human-typed name like "Boston University" correctly returns zero results (since RePORTER's internal name is `"BOSTON UNIVERSITY MEDICAL CAMPUS"`, not the colloquial name), with guidance to retry with `exact_match=False` to discover the real name via `matched_org_names`, then re-run precisely.

**Verified against the live API:** exact match on `"BOSTON UNIVERSITY MEDICAL CAMPUS"` for FY2024 returns 348 projects / $242,946,159 — isolating the correct single institution.

## 5. RePORTER's own website appears to apply additional undocumented default filtering

Manual comparison: the RePORTER website's default search for the same organization/year criteria returned different project counts across different filter combinations we tried (348 vs. 287 vs. 519 depending on whether "active projects only" and which exact organization grouping was applied) than the raw API returned for the equivalent query. This server's totals represent **all historical matching records returned by the raw API**, not the website's default view, which may pre-filter to active projects. This is documented explicitly rather than presented as a discrepancy-free match to the website.

## 6. `include_active_projects` behaves inconsistently when combined with `fiscal_years`

The upstream API's documented `include_active_projects` criterion, when combined with a `fiscal_years` filter, was observed to **increase** the result set rather than filter it (46,367 projects returned vs. 23,486 unfiltered, for the same base query) — the opposite of the expected filtering behavior.

**Fix:** We never send `include_active_projects` to the API. Instead, tools that support `active_only` filtering fetch the full result set (including the documented `is_active` response field, confirmed against the official API Data Elements PDF, page 37: *"An active project is whose latest Budget End Date has not occurred yet"*) and filter client-side. Slower, but correct and independently verifiable.

## 7. A missing parameter caused silent zero-results, not an error

`funding_trend_by_year` originally only accepted a free-text `topic` parameter. When an LLM agent attempted to get a year-by-year trend for an official spending category by passing the string `"spending_category:Cancer"` as the `topic` value (inferring this from how `summarize_funding_by_topic`'s response echoes that string), RePORTER correctly searched for that literal phrase and found nothing — returning a *successful* response with all-zero years, not an error. The agent correctly diagnosed this itself and fell back to free-text search, but the underlying tool gap was real.

**Fix:** `funding_trend_by_year` now accepts an explicit `spending_category` parameter, mirroring `summarize_funding_by_topic`, resolved through the same name/ID lookup. Regression-tested: `funding_trend_by_year(spending_category="Cancer", start_year=2022, end_year=2023)` now returns real non-zero data (15,185 projects / $4.99B in FY2022; 15,453 / $5.14B in FY2023).

**Lesson:** a tool that returns a well-formed but silently-empty result on a plausible-but-wrong input is more dangerous than one that errors clearly, because nothing signals the agent (or a human) that something went wrong.

## 8. Tool description clarity measurably affects agent efficiency — not just correctness

The question *"What are the five biggest Alzheimer's biomarker grants in Massachusetts in FY2024?"* was run three times against the same model (`databricks-gpt-5-5`, held constant) with the original `search_funded_projects` tool description. Tool calls per run: **1, 4, 1** (mean 2.0, stdev 1.7) — the model intermittently retried near-identical phrasings ("Alzheimer's biomarkers" → "Alzheimer's biomarker" → wildcard variants → "Alzheimer's disease biomarkers") apparently believing minor rewording might surface different results, when RePORTER's search already normalizes such variants server-side.

**Fix:** the `topic` parameter's description was updated to state explicitly that RePORTER handles phrasing/plural variants internally and that retrying with minor rewording will not change results. Re-measured under identical conditions (same model, same question, three runs): tool calls per run became **1, 1, 1** (mean 1.0, stdev 0.0).

**Significance:** this is a controlled, reproducible before/after result (one variable changed — a sentence in a tool description — with the model held constant) showing that tool description quality has a measurable effect on agent efficiency, not merely a theoretical one. Regression-guarded going forward (`eval/smoke_tests.py`, test `t9`: average tool calls per run must stay ≤1.5).

**Update (v0.14.0):** The specific numeric metric ("2.0 → 1.0") from the t9 harness has been dropped due to three harness defects (see `EVAL_VERDICTS.md` §3). The qualitative point is validated by real agent traces at v0.14.0: BC-1 (competitive renewal %) dropped from 32 calls to 1; BC-2 (top institution) dropped from 18 calls to 1. These are honest traces against `databricks-claude-sonnet-4-5`, not harness-measured.

## 9. Reasoning-tier model endpoints reject function-calling with default settings

Databricks-hosted reasoning models (endpoint names ending in `-sol`, `-luna`, `-terra`, `-astra`) returned errors when sent `tools` via the standard `/v1/chat/completions` interface with default reasoning settings. A non-reasoning chat-completion endpoint (`databricks-gpt-5-5`) was used instead for all agent-loop testing.

This matches a fix independently made in the [official hackathon template](https://github.com/GSA-TTS/mcp-hackathon-template/pull/9) ("Fix Databricks eval tool calls for reasoning endpoints"), which documents the same root cause (*"Databricks OpenAI reasoning endpoints reject function tools sent through `/v1/chat/completions`"*) and resolves it by using the `/v1/responses` endpoint instead for reasoning-tier models. We did not adopt that endpoint-switch fix, since our agent loop deliberately keeps reasoning-tier endpoints *selectable but flagged* in the model picker rather than switching protocols — our goal was to make the incompatibility visibly demonstrable, not invisible.

## 10. RePORTER’s `FullStudySection` field shape diverges from documentation in two places

The official API Data Elements documentation describes the `full_study_section` response object with a `group` field. The live API returns `group_code` instead. Additionally, the `name` field is not a human-readable study section name — it is a composite code string such as `"ZRG1-MOSS-R(02)"` or `"Special Emphasis Panel[ZEY1 VSN (07)]"`, constructed from the other fields.

**Verified:** `POST /v2/projects/search` with `include_fields: ["FullStudySection"]` for `appl_id` 10892807 returns:

```json
{
  "srg_code": "ZAI1",
  "srg_flex": null,
  "sra_designator_code": "ZL",
  "sra_flex_code": "M",
  "group_code": "J1",
  "name": "ZAI1-ZL-M(J1)"
}
```

The keys are `srg_code`, `srg_flex`, `sra_designator_code`, `sra_flex_code`, `group_code`, and `name` — six fields total. The docs list `group` where the actual field is `group_code`.

**Why it matters:** Any tool that groups or filters by study section must use the actual field names from the live response, not the documentation. Our `funded_projects_by_study_section` tool groups by `(srg_code, name)` and was verified against all 1,739 matching CRISPR gene editing records in FY2023, which distributed across 652 distinct study sections with `section_project_sum == total_projects` (no records lost in the grouping).

## 11. Parent/subproject counting: all_records exceeds whole_award by 10.1% (basis difference)

**Discovered in v0.8.0.** Per the NIH RePORTER Data Elements PDF: "For multi-project grants, Total_Cost includes funding for all the constituent subprojects." This means a parent award's `award_amount` already includes its children. Naively summing both parent and subproject records double-counts multi-project grants.

**Before (v0.7.0):** CRISPR gene editing FY2023 was reported as $921,543,173 across 1,739 matching records (parent + subproject) on the all_records basis. **After (v0.8.0):** Excluding 226 subproject records yields 1,513 parent records, of which 7 had missing amounts; the corrected whole_award total is $836,981,580 across the 1,506 contributing parent records — a $84,561,593 reduction. The naive all_records sum exceeds whole_award by 10.1% (= $84,561,593 / $836,981,580). This is an **all_records vs whole_award basis difference**, not a measured duplicate amount: 166 of the 226 excluded subprojects are orphans whose parent is not in the cohort, so their dollars are not duplicated within it.

The fix introduces `funding_basis` parameter (`"whole_award"` default, `"all_records"` for legacy behavior), appl_id deduplication across page boundaries, and explicit tracking of records with missing `award_amount` (excluded from totals, not zeroed to $0). This applies to `summarize_funding_by_topic`, `organization_funding_profile`, `funding_trend_by_year`, and `export_evidence_bundle`.

Verified with synthetic unit tests (`tests/test_counting.py`) against oracle values: a $1M parent with $300K + $200K children correctly sums to $1M (not $1.5M), page-boundary duplicates are deduped, and overlapping topic searches don't double-count shared records.

## 12. In-process response cache reduces warm-path latency from seconds to ~20ms

**Added in v0.9.0.** A 15-minute TTL cache on `post_json` (the shared HTTP layer) stores raw API responses keyed by SHA-256 of `(url, canonical-JSON-of-payload)`. Cache hits bypass the 1-req/sec rate limiter entirely.

**Cold path:** A `summarize_funding_by_topic` call for CRISPR FY2023 (1,739 matching records, 4 pages) takes approximately 4–6 seconds due to upstream latency plus mandatory 1-second spacing between pages.

**Warm path:** The same call returns in **~0.02s** — a >100x speedup — because all four pages are served from the in-process cache with no HTTP or rate-limiter overhead.

**Correctness under cache:** Two calls with different `funding_basis` (`whole_award` vs `all_records`) for the same query share the same cached raw API response (identical HTTP payloads) but produce different totals ($836,981,580 vs $921,543,173) because `aggregate_funding()` processes the raw data differently for each mode. This is verified by smoke test t18, which asserts both stability (cold == warm for same basis) and distinction (whole_award ≠ all_records). The cache can be disabled entirely via `NIH_MCP_CACHE_DISABLED=1` for testing or upstream-freshness requirements.

**Parallelisation:** `funding_trend_by_year` now fires all per-year queries concurrently via `asyncio.gather`. On a cold cache with a 3-year range, the rate limiter still serialises upstream requests to ~1 req/sec, but on warm cache all years resolve in parallel in ~20ms total. This reduces a 5-year trend query from ~25 seconds (sequential, 5 pages × 5 years) to under 1 second on warm cache.

## 13. Orphan subprojects are detected and flagged, not silently dropped

**Added in v0.10.1.** When `whole_award` mode excludes a subproject whose parent `core_project_num` is NOT among the cohort's parent records, that child is an **orphan**: its associated award-family investment is not reflected in the total (because the parent's whole-award amount, which includes this child, was never retrieved).

The frozen fixture ("CRISPR sickle cell" FY2024, 38 records) contains one orphan: appl_id 10992993, subproject of P50HD096723. Its parent is not a CRISPR sickle cell project, so excluding this child is correct — but the result cannot be labeled "exact" because an associated award family's investment may be missing. The note now states this explicitly.

**Orphan children block the internal `is_exact` check (not a returned field):** A query returning only orphan subprojects (or orphans alongside valid parents) will never claim the total is exact. This prevents the misleading scenario where a child-only probe returns "$0, complete=True, Total is exact."

A separate frozen fixture (`docs/demonstration_fixture_double_counting/`, U19AG068753 FY2024) provides the inspectable proof that subproject exclusion prevents real double-counting: 1 parent ($5,130,473) + 7 subprojects ($5,130,473) = $10,260,946 naive, correctly reduced to $5,130,473.

## 14. Correctness-against-ground-truth: all_records vs whole_award basis differences of 10.1% and 16.5%

**Regression-guarded (`tests/test_correctness.py`, drift-tolerant ±3%).** The v0.8.0 counting fix was initially validated in v0.9.0 against two independently-derived ground truths; headline figures are now regression-tested with drift-tolerant assertions (±3% band, reference date 2026-10-16) so they cannot silently drift unflagged:

| Topic (FY2023) | all_records (naive) | whole_award (corrected) | Delta | Basis difference (delta/whole_award) | Subprojects excluded | Missing amounts |
|---|---:|---:|---:|---:|---:|---:|
| CRISPR gene editing | $921,543,173 | $836,981,580 | $84,561,593 | 10.1% | 226 | 7 |
| Alzheimer’s disease | $4,685,253,389 | $4,020,899,771 | $664,353,618 | 16.5% | 931 | 133 |

The Alzheimer’s basis difference (16.5%) is larger than CRISPR’s (10.1%): NIH Alzheimer’s research includes more multi-component grants (U19, P01, etc.), so more subproject records are excluded (931 vs 226). Neither figure is all duplicate funding. Excluded orphan subprojects (166 of CRISPR’s 226; not documented for Alzheimer’s) carry real topical investment whose parent is absent from the cohort.

Additional correctness evidence (`tests/test_correctness.py`, 8 tests; five highlighted):

- **Ground-truth exact match**: “CRISPR sickle cell” FY2024 (38 records, independently fetched via curl and hand-computed) matches the tool’s whole_award total **to the dollar** ($19,790,134).
- **Double-counting proof**: U19AG068753 FY2024 — runs production `aggregate_funding` (both unprojected and AGG_FIELDS-projected) on raw fetched records, asserts whole_award equals parent-only sum and all_records exceeds it by the subproject delta. Proves the production code, not local arithmetic.
- **Provenance reproducibility**: Re-fetching `source_record_ids` from `export_evidence_bundle`, applying whole_award rules independently, and re-summing **reproduces the reported total exactly**.
- **Missing-amount honesty**: CRISPR FY2023 reports `records_with_missing_amount=7` and does not claim the total is “exact”; those records are excluded from the total, not zeroed to $0.
- **Cross-tool consistency**: `whole_award` < `all_records` with nonzero `subproject_excluded_count`, verified across multiple tools for the same query.

## 15. Tool-selection accuracy is stable across model families (agent-agnostic)

**Test:** 8 questions, each with a single expected first tool call, run against 3 models from different families: GPT-5-5 (OpenAI), Claude Sonnet 4-6 (Anthropic), and Llama 3.3 70B Instruct (Meta). Only the first tool call is evaluated — this isolates tool-selection from downstream execution.

**Results (2026-10-16, re-verified 2026-10-20 at v0.14.0):**

| Model | Accuracy (re-run) | Misses |
|---|---|---|
| databricks-gpt-5-5 | 7/8 (88%) | Q5: chose `check_investigator_overlap` instead of `investigator_portfolio` |
| databricks-claude-sonnet-4-6 | 7/8 (88%) | Q5: chose `check_investigator_overlap` (was 8/8 in prior run) |
| databricks-meta-llama-3-3-70b-instruct | 8/8 (100%) | — (was 7/8 in prior run — Q5 flipped to correct) |

Overall: **22/24 (92%)** correct across all trials. 6/8 cases had unanimous agreement across all 3 models. Headline score stable across runs; failure pattern shifted (Claude Q5 flipped from correct to incorrect; Llama Q5 flipped from incorrect to correct).

**Q5 disagreement analysis:** "What grants does Francis Collins currently hold?" — both GPT-5-5 and Claude Sonnet 4-6 selected `check_investigator_overlap` (designed for overlap/conflict detection, not portfolio listing). Only Llama selected the correct `investigator_portfolio`. All three tools accept PI-related inputs, so the confusion is understandable. This confirms Q5 is a genuine description-clarity ambiguity, not a model-specific quirk.

**Note:** The 8-question evaluation set predates `group_by`, `application_types`, `spending_category`, and `clinical_trials_lookup`. No question tests routing to or away from these newer capabilities. The 22/24 score covers the original tool surface only.

**Why it matters:** The tool descriptions are written once, in the MCP server, and consumed by any model. This finding confirms they are model-agnostic — accuracy is stable across GPT, Claude, and Llama families with no model-specific tuning. The two misses are description-clarity issues (tools with overlapping input schemas), not model-specific failures.

**Notebook reference:** `notebook-merged`, §14a–c (cells 31–34). Requires live model access — notebook-only, not in pytest suite.

## 16. Tool-selection is deterministic under repeat runs

**Test:** 3 representative questions (Q1: summarize_funding_by_topic, Q2: search_funded_projects, Q3: funding_trend_by_year) each run 5 times against GPT-5-5. This measures whether tool SELECTION is stable across repeats — distinct from the existing call-count efficiency guard (§13), which measures whether the number of tool calls is stable.

**Results (2026-10-16):** 3/3 stable. Every question selected the same tool across all 5 repeats — zero flickers.

| Question | Tool | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|---|---|
| Q1 (CRISPR sickle cell spending) | summarize_funding_by_topic | ✓ | ✓ | ✓ | ✓ | ✓ |
| Q2 (Alzheimer’s grants in MA) | search_funded_projects | ✓ | ✓ | ✓ | ✓ | ✓ |
| Q3 (long COVID trend) | funding_trend_by_year | ✓ | ✓ | ✓ | ✓ | ✓ |

**Why it matters:** Non-deterministic tool selection would undermine user trust: the same question could produce different workflows on different runs. This confirms the tool descriptions are unambiguous enough that the model’s tool-selection decision is stable even under LLM sampling randomness. Combined with the Q5 miss from Finding 14, this suggests the overall description set is solid, with `investigator_portfolio` vs `check_investigator_overlap` as the only known ambiguity.

**Notebook reference:** `notebook-merged`, §14d (cell 35). Notebook-only (requires model access).

## 17. Argument validity rate: 24/24 (100%) — re-verified at v0.14.0

**Test:** For each of the 8 TOOL_SELECTION_CASES × 3 models (24 trials total), capture the raw arguments the model generates and validate them against the tool’s input_schema:
- Required parameters present
- No unknown parameter names
- Correct types (string, integer, number, boolean, array)

**Results (2026-10-16; re-verified 2026-10-20 at v0.14.0):**

| Model | Argument validity rate |
|---|---|
| databricks-gpt-5-5 | 8/8 (100%) |
| databricks-claude-sonnet-4-6 | 8/8 (100%) |
| databricks-meta-llama-3-3-70b-instruct | 8/8 (100%) |

Overall: **24/24 (100%)**. In the re-run (2026-10-20), Llama selects `investigator_portfolio` for Q5 (correct tool), so the prior runtime-inadmissibility (`get_project_by_id({appl_id: null, core_project_num: null})`) no longer fires. Both the original 23/24 and the re-run 24/24 were honestly reported for their respective runs.

**Observations:** Models differ in how many optional parameters they populate (GPT-5-5 tends to include more optional parameters; Claude and Llama generate more minimal sets). All 24 calls are structurally valid (correct names, types, required params). The prior run's single failure (Llama Q5) was a schema design limitation: `get_project_by_id` marks both params as optional, so the at-least-one-of constraint is only discoverable from the description.

**Why it matters:** Combined with Finding 15 (tool-selection: 92%) and Finding 16 (determinism: 100%), these three metrics form a complete picture of tool-use quality.

**Notebook reference:** `notebook-merged`, §14e (cell 36). Notebook-only (requires model access).

## 18. No structural Common Fund / program filter in RePORTER API

NIH Common Fund programs (HuBMAP, SPARC, 4D Nucleome, etc.) are not
identifiable via a single API criterion. Investigated all available fields:

- **No `is_common_fund` flag** or program-level filter exists.
- **`funding_mechanism`**: "Other" for Common Fund — returns 85K+ results, useless as a discriminator.
- **`cfda_code`**: HuBMAP projects span 12+ CFDA codes (93.310, 93.172, 93.242, 93.351, ...).
  93.310 ("Trans-NIH Research Support") IS the Common Fund code but not all HuBMAP projects use it.
- **`opportunity_number` (FOA)**: HuBMAP spans 33+ FOAs from multiple ICs (RFA-RM-*, RFA-CA-*, PA-*, PAR-*).
  The API accepts `foa` as a criterion but matching a program requires knowing ALL its FOAs.
- **`agency_ic_admin`**: Most HuBMAP awards come from OD (Office of the Director), but not exclusively.

**Best available approximation:** NIH tags projects with program names in the
`terms` field (e.g., "Human BioMolecular Atlas Program"). Searching `terms` only
returns 494 all-years results; our tool's free-text search (`search_field: "all"`)
returns 561 — the 67 extra are projects that merely *mention* HuBMAP in their
abstract without being part of the program.

**Implication for the agent:** When a user asks "how many awards in the HuBMAP
program," the tool cannot give the authoritative program-level count. The keyword-
based approximation must be stated as the headline caveat, not buried. The tool
should say: "Based on keyword search, ~X projects mention HuBMAP. This is an
approximation — RePORTER does not expose a Common Fund program filter for exact
counts."

**Verified:** 2026-10-19. Free-text "HuBMAP" all-years=561, terms-only=494,
delta=67 mention-only projects. No `foa` filter, no `funding_mechanism` filter,
no `is_common_fund` field observed.

## 19. Server-side `group_by` faceting bypasses the 10,000-record pagination ceiling

**Added in v0.12.0.** `search_funded_projects` supports a `group_by` parameter (`application_type`, `organization`, `administering_ic`) that uses RePORTER's native faceting endpoint. When `group_by='application_type'` is used, the server sets `exclude_subprojects=True` and returns **deduped award counts** broken down by NIH application type code (1=New, 2=Competitive Renewal, 3=Extension, 4=Supplement, 5=Non-competing Continuation, 7=Merit Extension, 8=Merit Extension, 9=Other).

Critically, this path is **not subject to the 10,000-record pagination ceiling** described in Finding #1. Server-side faceting returns exact bucket counts for the entire matching cohort, regardless of size.

**Verified:** R01 FY2020 with `group_by='application_type'` returns 29,560 total deduped awards across 9 buckets, sum = 29,560 = total, 0 remainder (A5 LF-4/LF-10, 2026-10-19T23:42Z). Code 8 (Merit Extension) = 11 awards. This result would be unreachable via record-level pagination (29,560 > 10,000 ceiling).

**Why it matters:** Before `group_by`, answering "how many R01 competitive renewals in FY2020" required fetching records via `application_types=[2]`, which returns record counts (including subproject duplicates) and is capped at 10,000. The old approach reported 397 (client-side count from a single 500-record page). `group_by` returns 1,089 deduped awards — a 2.7x correction. This was the root cause of behavioral case BC-4 (P41 renewal trend), which now uses `group_by` and produces correct deduped counts (FY2015: 13, FY2025: 1) instead of inflated record counts (85, 7).

## 20. RCDC category ID 55 = Arthritis; RCDC-vs-free-text gap quantified

NIH's Research, Condition, and Disease Categorization (RCDC) system assigns numeric IDs to spending categories. For Arthritis, the RCDC category ID is **55**.

**RCDC vs. free-text divergence for Arthritis FY2023:**

| Method | Projects | Total |
|---|---|---|
| RCDC category 55 ("Arthritis") | 658 | $291,641,663 |
| Free-text search "arthritis" | 1,403 | $708,609,739 |
| **Gap** | **2.1x projects, 2.4x dollars** | |

This is the same structural divergence documented in Finding #3 for Long COVID (4.25x) and in Finding #14 for Alzheimer's. The RCDC figure represents projects curated into the official spending category; free-text captures any project that mentions the term, including tangential references.

**Verified:** A5 LF-8a/LF-8b (2026-10-19T23:47Z). The `spending_categories` resource lists all 39 curated RCDC categories including Arthritis (ID 55). The server's `config.py` maps `"Arthritis"` → 55.

## 21. `application_types` filter returns record counts, not deduped award counts

When `search_funded_projects` is called with `application_types=[2]` (competitive renewals), the returned count includes **all matching records**, including subproject duplicates. For center grants (P30, P41, P50, U54), one award fans out into many subproject records, so the count overcounts awards by 5–100x.

**Example:** P41 FY2015 with `application_types=[2]` returns 85 records. `group_by='application_type'` with `exclude_subprojects=True` returns 13 deduped awards. The 85-to-13 ratio reflects subproject fan-out in multi-component P41 awards.

**Fix (v0.14.0):** The `application_types` parameter description now includes a WARNING: "RECORD-LEVEL counts: this filter returns RAW RECORD counts... For 'how many awards/renewals' questions, use `group_by='application_type'` instead." The `group_by` parameter description states it is the PREFERRED path for award-count questions.

**Verified:** A5 LF-9a (P41 FY2015: 85 records vs. 13 deduped awards), A5 LF-9b (P41 FY2025: raw records vs. 1 deduped award). Behavioral case BC-4 now produces correct deduped counts exclusively.
