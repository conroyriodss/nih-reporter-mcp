# Findings

Documented, reproducible discoveries made while building and testing this server. Each was verified against either the official NIH RePORTER API documentation, a raw API call bypassing our tool layer, or a manual cross-check against reporter.nih.gov's search UI.

## 1. Our paginator retrieves at most 10,000 records per query

Our paginator is configured to fetch up to 20 pages × 500 records = 10,000 records. During development we observed that the upstream RePORTER API also rejects high offsets (returning empty results or errors at offset ≥ 15,000), suggesting an upstream ceiling, but our test suite only verifies our own configured cap — not the upstream limit directly. A broad query like "cancer" in FY2023 has 23,486 true matches but only 10,000 are retrievable through our paginator.

**Why it matters:** A naive implementation either silently truncates (reporting a wrong total as if it were complete) or crashes on the offset ceiling. Every aggregating tool here (`summarize_funding_by_topic`, `funding_trend_by_year`, `organization_funding_profile`) returns an explicit `complete: bool` flag and a `note` explaining the shortfall when the cap is hit, rather than hiding it.

**Verified:** `summarize_funding_by_topic(topic="cancer", fiscal_years=[2023])` → `total_matching_projects=23486, projects_aggregated=10000, complete=False`.

## 2. The 500-record MVP cap materially understated real totals

Before implementing full pagination, an early version capped aggregation at a single 500-record page. For "CRISPR gene editing" FY2023, this produced **$580M** from 500 records. Full pagination across all 1,739 records returned **$921.5M on the all_records basis** (since superseded by the whole_award corrected figure of $837M in Finding 11). The 500-record cap understated even the naive all_records total by 37% (= ($921.5M − $580M) / $921.5M), and understated the corrected whole_award total by 30.7% (= ($837M − $580M) / $837M). This motivated full pagination as a correctness requirement, not an optimization.

## 3. NIH's official RCDC spending categories diverge sharply from free-text keyword search

For "Long COVID" in FY2023:

| Method | Matching projects | Total award amount |
|---|---:|---:|
| Official RCDC category ("Long COVID", ID 5194) | 154 | $209,603,849 |
| Free-text search for "long covid" | 1,148 | $891,742,057 |

A 4.25x difference. The RCDC category is NIH's own curated, congressionally-mandated classification; free-text search catches any project that merely mentions the term, including tangential references. Neither number is "wrong" — they answer different questions — but presenting one as if it were the only truth would mislead. `summarize_funding_by_topic` accepts either method explicitly (`topic` for free-text, `spending_category` for the official category) and both paths are available as distinct tool calls, so an agent (or a human) can compare them rather than being forced into one framing.

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

**Why it matters:** Any tool that groups or filters by study section must use the actual field names from the live response, not the documentation. Our `study_section_workload` tool groups by `(srg_code, name)` and was verified against 1,739 CRISPR gene editing projects in FY2023, which distributed across 652 distinct study sections with `section_project_sum == total_projects` (no projects lost in the grouping).

## 11. Parent/subproject double-counting inflated funding totals by 10.1%

**Discovered in v0.8.0.** Per the NIH RePORTER Data Elements PDF: "For multi-project grants, Total_Cost includes funding for all the constituent subprojects." This means a parent award's `award_amount` already includes its children. Naively summing both parent and subproject records double-counts multi-project grants.

**Before (v0.7.0):** CRISPR gene editing FY2023 was reported as $921,543,173 across 1,739 records (parent + subproject) on the all_records basis. **After (v0.8.0):** Excluding 226 subproject records and 7 records with missing amounts, the corrected whole_award total is $836,981,580 across 1,513 parent records — a $84,561,593 reduction. The naive all_records sum overstated the corrected figure by 10.1% (= $84,561,593 / $836,981,580).

The fix introduces `funding_basis` parameter (`"whole_award"` default, `"all_records"` for legacy behavior), appl_id deduplication across page boundaries, and explicit tracking of records with missing `award_amount` (excluded from totals, not zeroed to $0). This applies to `summarize_funding_by_topic`, `organization_funding_profile`, `funding_trend_by_year`, and `export_evidence_bundle`.

Verified with synthetic unit tests (`tests/test_counting.py`) against oracle values: a $1M parent with $300K + $200K children correctly sums to $1M (not $1.5M), page-boundary duplicates are deduped, and overlapping topic searches don't double-count shared records.

## 12. In-process response cache reduces warm-path latency from seconds to ~20ms

**Added in v0.9.0.** A 15-minute TTL cache on `post_json` (the shared HTTP layer) stores raw API responses keyed by SHA-256 of `(url, canonical-JSON-of-payload)`. Cache hits bypass the 1-req/sec rate limiter entirely.

**Cold path:** A `summarize_funding_by_topic` call for CRISPR FY2023 (1,739 projects, 4 pages) takes approximately 4–6 seconds due to upstream latency plus mandatory 1-second spacing between pages.

**Warm path:** The same call returns in **~0.02s** — a >100x speedup — because all four pages are served from the in-process cache with no HTTP or rate-limiter overhead.

**Correctness under cache:** Two calls with different `funding_basis` (`whole_award` vs `all_records`) for the same query share the same cached raw API response (identical HTTP payloads) but produce different totals ($836,981,580 vs $921,543,173) because `aggregate_funding()` processes the raw data differently for each mode. This is verified by smoke test t18, which asserts both stability (cold == warm for same basis) and distinction (whole_award ≠ all_records). The cache can be disabled entirely via `NIH_MCP_CACHE_DISABLED=1` for testing or upstream-freshness requirements.

**Parallelisation:** `funding_trend_by_year` now fires all per-year queries concurrently via `asyncio.gather`. On a cold cache with a 3-year range, the rate limiter still serialises upstream requests to ~1 req/sec, but on warm cache all years resolve in parallel in ~20ms total. This reduces a 5-year trend query from ~25 seconds (sequential, 5 pages × 5 years) to under 1 second on warm cache.

## 13. Correctness-against-ground-truth: overstatement ranges from 9% to 14% across topics

**Verified in v0.9.0 (`tests/test_correctness.py`).** The v0.8.0 counting fix was validated against two independently-derived ground truths:

| Topic (FY2023) | all_records (naive) | whole_award (corrected) | Delta | Overstatement (delta/corrected) | Subprojects excluded | Missing amounts |
|---|---:|---:|---:|---:|---:|---:|
| CRISPR gene editing | $921,543,173 | $836,981,580 | $84,561,593 | 10.1% | 226 | 7 |
| Alzheimer’s disease | $4,685,253,389 | $4,020,899,771 | $664,353,618 | 16.5% | 931 | 133 |

The Alzheimer’s overstatement (16.5%) is larger than CRISPR’s (10.1%) because NIH Alzheimer’s research includes more multi-component grants (U19, P01, etc.) whose subprojects inflate the naive sum by a greater proportion.

Additional correctness evidence (`tests/test_correctness.py`, 5 tests):

- **Ground-truth exact match**: “CRISPR sickle cell” FY2024 (38 records, independently fetched via curl and hand-computed) matches the tool’s whole_award total **to the dollar** ($19,790,134).
- **Double-counting proof**: U19AG068753 FY2024 — 1 parent ($5,130,473) + 7 subprojects (sum $5,130,473) = $10,260,946 naive. The delta ($5,130,473) is **exactly** the summed subproject amounts, proving the fix removes real double-counted dollars.
- **Provenance reproducibility**: Re-fetching `source_record_ids` from `export_evidence_bundle`, applying whole_award rules independently, and re-summing **reproduces the reported total exactly**.
- **Missing-amount honesty**: CRISPR FY2023 reports `records_with_missing_amount=7` and does not claim the total is “exact”; those records are excluded from the total, not zeroed to $0.
- **Cross-tool consistency**: `whole_award` < `all_records` with nonzero `subproject_excluded_count`, verified across multiple tools for the same query.
