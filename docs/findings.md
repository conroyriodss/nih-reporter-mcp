# Findings

Documented, reproducible discoveries made while building and testing this server. Each was verified against either the official NIH RePORTER API documentation, a raw API call bypassing our tool layer, or a manual cross-check against reporter.nih.gov's search UI.

## 1. RePORTER has a hard 10,000-record retrieval ceiling, undocumented in practice

RePORTER's API caps `offset` at 14,999 for projects (9,999 for publications), and no combination of pagination can retrieve more than 10,000 total records for a single query, regardless of how many truly match. A broad query like "cancer" in FY2023 has 23,486 true matches but only 10,000 are retrievable.

**Why it matters:** A naive implementation either silently truncates (reporting a wrong total as if it were complete) or crashes on the offset ceiling. Every aggregating tool here (`summarize_funding_by_topic`, `funding_trend_by_year`, `organization_funding_profile`) returns an explicit `complete: bool` flag and a `note` explaining the shortfall when the ceiling is hit, rather than hiding it.

**Verified:** `summarize_funding_by_topic(topic="cancer", fiscal_years=[2023])` → `total_matching_projects=23486, projects_aggregated=10000, complete=False`.

## 2. The 500-record MVP cap materially understated real totals

Before implementing full pagination, an early version capped aggregation at a single 500-record page. For "CRISPR gene editing" FY2023, this produced an estimated total of **$580M**. The paginated, exact version returns **$921.5M** — a 59% understatement from the capped version, for a query that comfortably fits under the true 10,000-record ceiling (1,739 actual matches). This motivated full pagination as a correctness requirement, not an optimization.

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
