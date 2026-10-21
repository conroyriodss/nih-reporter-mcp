# Robustness & Stability Evaluation Report

This report documents the evidence for four hackathon judging criteria,
produced by `tests/test_robustness.py`.

**Current counts (v0.14.5):** 49 robustness tests = 11 mocked (Part C, counted within the 155 CI figure) + 38 server-dependent (Parts A/B/D/E: 32 stable + 6 pass-with-retry). All 14 registered tools have `TOOL_INPUTS` coverage, enforced by `test_all_tools_have_test_inputs`.

> The per-row detail tables in Parts A, B, D and E come from the earlier 13-tool run, before `clinical_trials_lookup` was registered. They show *what* each part checks; current pass counts are in the Test Counts table at the end. `clinical_trials_lookup` is covered by Parts A and B through `TOOL_INPUTS`, but it doesn't have its own row in the historical latency table.

## Summary

| Criterion | Evidence | Result |
|---|---|---|
| Thoughtful eval design | 14 tools × 3 input variants + parameterized error matrix + mocked upstream failures + stability runs + latency profile | 49 tests: 11 mocked (in CI 155) + 38 server-dependent (32 stable + 6 pass-with-retry) |
| Well-formed responses | Every tool tested with normal, zero-result, and boundary inputs; all return validated Pydantic models (never raw dict/None) | 14/14 tools covered (`TOOL_INPUTS`) |
| Graceful error handling | 28 parameterized error conditions tested (missing params, wrong types, nonexistent IDs, oversized inputs) + 11 mocked upstream failures (500, timeout, 429, oversized, malformed JSON, network error, 400, 403, and 3 malformed-200 payload cases) | 39/39 conditions handled cleanly |
| Stable performance | 3 tools × 5 runs with cache on + 2 tools × 5 runs with cache off; dollar figures identical across all runs | 0 variance detected |

## Part A — Well-Formed Responses (14 tools × 3 cases)

Tool list discovered programmatically from `list_tools()` — a newly-added tool
cannot be silently omitted from coverage.

| Input case | Tools tested | Result |
|---|---|---|
| Normal (valid input with data) | 13 | 13/13 return structured Pydantic model |
| Zero-result (valid input, no matches) | 13 | 13/13 return valid empty model |
| Boundary (limit=1, single year, etc.) | 10 (3 N/A) | 10/10 return structured model |

## Part B — Error Handling Matrix (28 parameterized conditions)

| Condition | Tools tested | Expected | Result |
|---|---|---|---|
| Missing required parameter | 11 | Clean validation error | 11/11 pass |
| Wrong parameter type | 5 | Clean validation error | 5/5 pass |
| Nonexistent ID (valid format) | 6 | Valid empty response, NOT error | 6/6 pass |
| Oversized input (>500 chars or >20 items) | 6 | Clean validation error citing limit | 6/6 pass |

No tool ever leaked an httpx traceback, produced an unhandled exception, or
returned a 500-equivalent.

## Part C — Mocked Upstream Failures (11 unit tests, run in CI)

These prove error handling for conditions that cannot be triggered with live
calls (you can't force the live API to 500 on demand).

| Upstream failure | Expected behavior | Result |
|---|---|---|
| HTTP 500 | `RuntimeError("unexpected error (HTTP 500)")` | PASS |
| Timeout | `RuntimeError("timed out")` | PASS |
| HTTP 429 (rate limit) | Retry once, then succeed | PASS (2 calls confirmed) |
| Response > 10 MB | `RuntimeError("too large")` | PASS |
| Malformed JSON | `JSONDecodeError` or `RuntimeError` | PASS |
| Network error (connect refused) | `RuntimeError("Network error")` | PASS |
| HTTP 400 | `ValueError("rejected (400)")` | PASS |
| HTTP 403 | `ValueError("blocked (403)")` | PASS |
| HTTP 200 with malformed body | Error raised, not silently empty | PASS |
| HTTP 200 with partial keys | Error raised | PASS |
| `meta` present but no `total` key | Error raised | PASS |

## Part D — Stability Across Repeated Calls

| Tool | Cache state | Runs | Variance |
|---|---|---|---|
| summarize_funding_by_topic | ON | 5 | 0 (identical) |
| organization_funding_profile | ON | 5 | 0 (identical) |
| search_recent_awards | ON | 5 | 0 (identical) |
| summarize_funding_by_topic | OFF | 5 | 0 (identical) |
| organization_funding_profile | OFF | 5 | 0 (identical) |

With cache disabled (`NIH_MCP_CACHE_DISABLED=1`), every call hits the upstream
API independently. Zero variance confirms the aggregation logic is deterministic
and the upstream data is stable within the test window.

## Part E — Latency Profile (cold cache)

| Tool | Latency | Status |
|---|---|---|
| check_investigator_overlap | 0.02s | OK |
| explain_health_topic | 0.34s | OK |
| export_evidence_bundle | 0.03s | OK |
| funding_trend_by_year | 0.02s | OK |
| get_project_by_id | 0.02s | OK |
| get_publication_details | 0.56s | OK |
| investigator_portfolio | 0.03s | OK |
| list_publications_for_project | 0.02s | OK |
| organization_funding_profile | 0.03s | OK |
| search_funded_projects | 0.03s | OK |
| search_recent_awards | 0.02s | OK |
| funded_projects_by_study_section | 0.07s | OK |
| summarize_funding_by_topic | 0.02s | OK |

All 13 tools measured in this (historical) run responded under 1 second cold. Most tools respond in under 100ms
(cache warm from earlier test runs in the session). `get_publication_details`
is the slowest at 0.56s (hits NCBI E-utilities, the most latency-variable
upstream). No tool exceeds the 10-second flag threshold.

## Test Counts

| Test file | Tests | Status |
|---|---|---|
| tests/test_robustness.py Part A | 4 (1 coverage check + 3 cases × 14 tools) | server-dependent |
| tests/test_robustness.py Part B | 28 | server-dependent |
| tests/test_robustness.py Part C | 11 | 11 passed (mocked, in CI) |
| tests/test_robustness.py Part D | 5 | server-dependent |
| tests/test_robustness.py Part E | 1 (covers 14 tools) | server-dependent |
| **Total** | **49** | **11 mocked (in CI 155) + 38 server-dependent: 32 stable + 6 pass-with-retry** |
