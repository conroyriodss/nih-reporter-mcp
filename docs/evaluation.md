# NIH RePORTER MCP Server — Evaluation Document

**Project:** NIH RePORTER MCP Server 
**Team:** Rich Conroy (conroyri@nih.gov), NIH/OD/ODSS 
**Hackathon:** GSA MCP Server and AI Agent Government Hackathon 
**Version:** v0.10.2-dev 
**Date:** October 16, 2026

---

## 1. Testing Methodology

### 1.1 Test Architecture — Three Independent Tiers

All tests are in the `tests/` directory and runnable with standard `pytest`. The tiers are designed so that each can run independently without the others.

#### Tier 1: Model-Free CI (GitHub Actions, every push/PR)

**Status: ✅ Verified — 75 passed + 2 xfailed**

| Test file | Tests | What it covers |
|---|---|---|
| `tests/test_counting.py` | 20 passed + 2 xfailed | Synthetic-fixture unit tests for `aggregate_funding()`: subproject exclusion, `appl_id` deduplication, missing-amount tracking, `is_exact` flag, page-boundary dedup, multi-year rollup, whole_award vs all_records basis separation, IC-attribution edge cases (2 xfail — known upstream limitation) |
| `tests/test_security.py` | 21 passed | Host-allowlist enforcement (only `api.reporter.nih.gov`, `eutils.ncbi.nlm.nih.gov`, `wsearch.nlm.nih.gov` allowed), input-size guards on topic length and fiscal-year array size, parameter type validation |
| `tests/test_prompt_contracts.py` | 24 passed | Every prompt (`funding_overview`, `institution_report`, `compare_rcdc_vs_freetext`, `research_landscape_summary`, `portfolio_brief`, `other_support_review`, `investment_to_outputs`, `explain_funding_landscape`, `follow_the_evidence`) references only tools that actually exist, and every tool referenced uses parameter names that match the tool's actual schema |
| `tests/test_robustness.py::TestPartC` | 10 passed | Mocked upstream failure handling: HTTP 500 → RuntimeError, 429 → retry-then-succeed, timeout → RuntimeError, oversized response → rejection, network error → RuntimeError, HTTP 400/403 → ValueError, malformed JSON → error, malformed-200-with-partial-keys → error |

**Evidence tier: Verified.** Run command:
```bash
PYTHONPATH=src pytest tests/test_counting.py tests/test_security.py \
  tests/test_prompt_contracts.py \
  tests/test_robustness.py::TestPartC_MockedUpstreamFailures -v
```

CI configuration: `.github/workflows/ci.yml` — runs on Python 3.11 and 3.12 on every push to `main` and every PR.

#### Tier 2: Live-Server Integration (requires running MCP server)

**Status: ✅ Verified — 18/18 smoke tests passed**

The notebook (`notebook-merged`, Cell 12) runs 18 automated assertions against the **live NIH RePORTER API** (not mocked). Each test calls a tool via the MCP protocol and validates the structured response:

| Test | What it verifies |
|---|---|
| t1 | Full-pagination aggregation: CRISPR gene editing FY2023 == 1,739 matching projects, $836,981,580 whole_award, complete=True. Note: `is_exact=False` — 166 orphan subprojects (CRISPR-mentioning sub-components of non-CRISPR umbrella grants) and 7 records with missing amounts are flagged transparently. |
| t2 | 10,000-record retrieval cap honestly flagged (complete=False, aggregated=10,000 of 23,486 matching) |
| t3 | Exact org-name match isolates a single institution (Boston University Medical Campus: 348 projects) |
| t4 | Official RCDC spending category vs. free-text search: documented divergence ($199.6M RCDC vs. $891.7M free-text for "long covid") |
| t5 | Empty topic input raises clean validation error |
| t6 | SQL-injection-style input: clean 403 handling, no leaked traceback |
| t7 | Cross-tool consistency: whole_award ($836.98M) < all_records ($921.54M), subprojects_excluded=226 |
| t8 | `funding_trend_by_year` accepts `spending_category` directly (regression test) |
| t9 | Tool-call efficiency: avg 1.0 calls/question (regression threshold: ≤1.5) |
| t10 | `check_investigator_overlap` end-to-end with valid structure |
| t11 | `exclude_project_num` strictly reduces result count (11 → 9) |
| t12 | `funded_projects_by_study_section` groups correctly, section counts ≤ total |
| t13 | `search_recent_awards` respects limit, all results have reporter_url |
| t14 | Provenance populated, counting-unit basis stated, aggregated ≥ 1,400 |
| t15 | `export_evidence_bundle` returns inspectable source record IDs with reproduction note |
| t16 | `explain_health_topic` returns MedlinePlus summary for common condition |
| t17 | `explain_health_topic` handles no-match cleanly (not an error) |
| t18 | Cache preserves correctness: whole_award ≠ all_records, warm latency ~0.02s |

Additionally, `tests/test_correctness.py` contains 6 tests that verify funding arithmetic against independently-derived ground truth (requires a running MCP server).

**Evidence tier: Verified.** Notebook Cell 12 output shows "TOTAL: 18/18 passed" (run October 16, 2026).

#### Tier 3: Multi-Model Agent Evaluation (Databricks notebook only)

**Status: ✅ Verified — results below**

Notebook cells 32–36 run a structured evaluation of tool-selection accuracy across three model families to demonstrate that the server's tool descriptions are agent-agnostic:

| Eval | Result |
|---|---|
| Tool-selection accuracy (8 questions × 3 models) | 22/24 correct (92%) |
| Per-model: GPT-5-5 | 7/8 (88%) |
| Per-model: Claude Sonnet 4-6 | 8/8 (100%) |
| Per-model: Llama 3.3 70B Instruct | 7/8 (88%) |
| Unanimous correct (all 3 agree) | 7/8 |
| Tool-selection determinism (3 questions × 5 repeats, GPT-5-5) | 3/3 stable |
| Argument validity (8 questions × 3 models) | 24/24 (100%) |

**Disagreement detail:** Q5 ("What grants does Francis Collins currently hold?") — GPT-5-5 selected `check_investigator_overlap`, Llama selected `get_project_by_id`, only Claude selected the expected `investigator_portfolio`. This represents a description-clarity improvement opportunity, not a server defect.

**Evidence tier: Verified.** Notebook cells 32–36 output (run October 16, 2026).

### 1.2 Ground Truth Methodology

The CRISPR gene editing FY2024 ground truth fixture (`tests/fixtures/crispr_sickle_cell_fy2024.json`) was independently constructed by:
1. Querying RePORTER API directly with known parameters
2. Computing the expected total manually from the raw response records
3. Verifying the server's output matches: **$19,790,134.00** (exact fixture match confirmed October 16, 2026)

See `docs/ground_truth_methodology.md` for the full procedure.

---

## 2. Performance Metrics

### 2.1 Headline Figures (Live-Verified October 16, 2026)

| Metric | Value | Evidence |
|---|---|---|
| CRISPR FY2023 whole_award total | $836,981,580 | Verified: notebook Cell 24 + t1 |
| CRISPR FY2023 all_records total | $921,543,173 | Verified: notebook Cell 24 + t7 |
| Naive-sum overstatement | 10.1% | ($921.5M − $837.0M) / $837.0M |
| CRISPR sickle cell FY2024 (fixture) | $19,790,134.00 | Verified: exact match |
| Total matching projects (CRISPR FY2023) | 1,739 | Verified: t1 |
| Projects aggregated (whole_award) | 1,506 | 1,739 − 226 subprojects − 7 missing amounts |
| Subprojects excluded | 226 | Verified: t7 |
| Records with missing amounts | 7 | Verified: Cell 24 |
| Deduplication (appl_id) | 0 for this query | Verified: Cell 24 |
| 10,000-record API ceiling | Honestly flagged | Verified: t2 (complete=False) |

### 2.2 Tool-Call Efficiency

| Metric | Before fix | After fix |
|---|---|---|
| Avg tool calls per question | 2.0 (stdev 1.7) | 1.0 (stdev 0.0) |
| Root cause | `search_funded_projects` docstring ambiguity caused LLM to issue redundant near-duplicate queries | Single docstring clarification |
| Model held constant | databricks-gpt-5-5 | databricks-gpt-5-5 |

### 2.3 Response Latency

| Path | Latency |
|---|---|
| Cold (first query, no cache) | 4–6 seconds |
| Warm (15-minute TTL cache hit) | ~0.02 seconds |
| Improvement factor | >100× |

### 2.4 Pagination Completeness

The server implements full pagination (`PAGE_SIZE=500`, up to `MAX_PAGES=20`) to retrieve up to 10,000 records per query. For CRISPR FY2023 (1,739 records across 4 pages), pagination delivers **complete=True** — every matching record is included. For very large result sets (e.g., "cancer" with 23,486 matches), the 10,000-record API ceiling is honestly reported via **complete=False** with `total_matching` and `projects_aggregated` fields.

### 2.5 Investigator Overlap Pagination

The `check_investigator_overlap` tool was upgraded from a single 100-record call to full `paginate_all()`. Result model includes `total_matching` and `complete` fields. Proven with Francis Collins (102 records > old 100-cap): now complete=True, all 102 examined.

---

## 3. Security Considerations

### 3.1 Input Validation (21 tests in test_security.py)

- **Host allowlist**: Only three domains are permitted for outbound HTTP: `api.reporter.nih.gov`, `eutils.ncbi.nlm.nih.gov`, `wsearch.nlm.nih.gov`. Any other host raises `ValueError`.
- **Topic length guard**: Topics exceeding 2,000 characters are rejected.
- **Fiscal year array size**: Arrays exceeding 20 elements are rejected.
- **Type validation**: String where integer expected (and vice versa) raises `TypeError`.

### 3.2 Injection Handling

SQL-injection-style inputs (e.g., `cancer" OR "1"="1`) are passed through to the upstream API, which returns HTTP 403. The server catches this and raises a clean `ValueError` with a user-readable message — no raw traceback, no API internals, no HTML error pages.

Verified: smoke test t6.

### 3.3 Web Application Security (Databricks App)

- **Authentication**: SDK OAuth (`w.config.authenticate()`) with PAT fallback — no hardcoded tokens.
- **Global exception handler**: `@app.exception_handler(Exception)` always returns JSON, never HTML error pages (prevents the "Unexpected token 'I'" frontend crash from unhandled 500s).
- **Smart truncation**: `_truncate_tool_result()` uses 3-tier truncation that preserves trust-critical fields (`complete`, `note`, `funding_basis`, `counting_unit`, `records_with_missing_amount`) while trimming bulky arrays. Verified: all trust signals survive truncation.

### 3.4 No Credentials in Code

All credentials (Databricks PAT, GitHub PAT) are stored in workspace secrets or environment variables, never in source files. The `.gitignore` excludes common credential file patterns.

### 3.5 Deployed App Access Model

The Databricks App (`mcp-nih-reporter`) is accessible to **authenticated workspace users via browser** only. It is behind an OAuth/OIDC gate managed by the Databricks platform — there is no public API endpoint reachable by an external automated MCP client without workspace credentials. This is a platform constraint, not a design limitation.

The app exposes two demonstration surfaces:

1. **Evidence Bundle** (always works): Enter any NIH research topic and fiscal year to retrieve a fully-provenanced funding total with reproduction steps, source record IDs, and deduplication metadata. This exercises the core MCP tool pipeline end-to-end without requiring LLM access.

2. **Ask agent loop** (requires serving endpoint): Sends a natural-language question to a Databricks-hosted LLM which autonomously selects and chains the MCP tools. Requires that the app's service principal has `CAN_QUERY` access to the `databricks-gpt-5-5` serving endpoint (declared in `app.yaml` resources). If the agent returns an error, the Evidence Bundle above remains the primary verified demonstration.

**Primary reproducible artifacts** (available without workspace access):
- The public GitHub repository (`github.com/conroyriodss/nih-reporter-mcp`) containing all source, tests, and documentation
- The companion Databricks notebook (`notebook-merged`) with frozen execution outputs from October 16, 2026
- The ground truth fixtures (`tests/fixtures/crispr_sickle_cell_fy2024.json`, `docs/demonstration_fixture/`, `docs/demonstration_fixture_double_counting/`)

Any evaluator can reproduce the MCP server locally with `uv run python main.py` — no Databricks workspace, API key, or authentication is required for the underlying NIH RePORTER / NCBI APIs.

### 3.6 Vulnerability Disclosure

See `SECURITY.md` for the project's vulnerability disclosure policy.

---

## 4. Lessons Learned

### 4.1 The Double-Counting Trap

The single most impactful finding: naively summing all award amounts from RePORTER **overstates funding by 10.1%** for CRISPR FY2023 ($921.5M all_records vs. $837.0M whole_award). The cause: multi-component awards (U-mechanisms, P-mechanisms) create parent + child records, each carrying an `award_amount` field. Summing all records double-counts.

**Solution:** The `whole_award` funding basis excludes subproject records (activity codes starting with specific prefixes), deduplicates by `appl_id`, and tracks records with missing amounts. The `is_exact` property on `AggResult` returns True only when `records_with_missing_amount == 0 AND NOT has_unresolved_conflicts AND NOT orphan_children`.

This is documented in `docs/findings.md` (Finding #1) and tested in `test_counting.py` (20 tests).

### 4.2 Official Category vs. Free-Text Search Divergence

NIH's RCDC spending categories and free-text keyword searches return **dramatically different totals** for the same disease area. For "long covid" in FY2023: RCDC category reports $199.6M while free-text search finds $891.7M. Neither is "wrong" — they measure different things (curated categorization vs. text occurrence).

**Solution:** `compare_rcdc_vs_freetext` prompt explicitly runs both methods and presents both numbers with a documented explanation.

### 4.3 Tool Description Quality Drives Agent Accuracy

The tool-call efficiency regression (2.0 → 1.0 calls/question) was caused and fixed by a **single docstring edit** to `search_funded_projects`. Before the fix, the description was ambiguous enough that the LLM issued a broad search followed by a narrower re-query.

The multi-model eval confirms this: tool descriptions clear enough for one model family are clear enough for all three tested (92% accuracy across GPT, Claude, and Llama families).

### 4.4 Honest Reporting Over Silent Failure

Design principle: every tool output includes metadata that lets the consumer assess trustworthiness. The `complete` flag, `total_matching` vs. `projects_aggregated` counts, `funding_basis`, and `records_with_missing_amount` are always present — the agent (or human reviewer) can decide how to interpret a partial result rather than receiving a silently truncated answer.

The evidence-bundle tool (`export_evidence_bundle`) takes this further: it returns the query criteria, source record IDs (up to 500, with a count of the true total), and a reproduction note so any claim can be independently verified.

### 4.5 Cache Correctness Requires Basis Separation

The 15-minute TTL cache on `post_json` must never collide results from different `funding_basis` values (whole_award vs. all_records). Cache keys include the full payload hash, and smoke test t18 proves that the same query with different bases returns different (correct) amounts, even when one is served from cache.

### 4.6 Mocked vs. Live Tests Serve Different Purposes

TestPartC (mocked upstream failures) catches regressions in error-handling code without network access — ideal for CI. But only live-server tests (t1–t18) catch real-world issues like pagination edge cases, actual API response format changes, and cache correctness under realistic payloads. Both tiers are necessary.

---

## Appendix: File Inventory

| Artifact | Path | Verified |
|---|---|---|
| Source code | `src/nih_reporter_mcp/` | ✅ |
| 13 tools | `src/nih_reporter_mcp/tools/` | ✅ |
| 9 prompts | `src/nih_reporter_mcp/prompts/` | ✅ |
| 2 resources | `src/nih_reporter_mcp/resources/` | ✅ |
| Unit tests (model-free) | `tests/test_counting.py`, `test_security.py`, `test_prompt_contracts.py` | ✅ 65p + 2xf |
| Robustness tests (mocked) | `tests/test_robustness.py::TestPartC` | ✅ 10p |
| Correctness tests (live) | `tests/test_correctness.py` | ✅ 6 tests |
| Robustness tests (live) | `tests/test_robustness.py` Parts A/B/D/E | ✅ 38 tests |
| CI workflow | `.github/workflows/ci.yml` | ✅ |
| Ground truth fixture | `tests/fixtures/crispr_sickle_cell_fy2024.json` | ✅ |
| Smoke tests | `eval/smoke_tests.py` | ✅ 18/18 |
| Notebook (demo + evals) | `notebook-merged` | ✅ |
| Architecture doc | `docs/architecture.md` | ✅ |
| Findings doc | `docs/findings.md` | ✅ |
| Robustness doc | `docs/robustness.md` | ✅ |
| Roadmap | `docs/roadmap.md` | ✅ |
| Demo script | `docs/demo_script.md` | ✅ |
| Ground truth methodology | `docs/ground_truth_methodology.md` | ✅ |
| Demonstration fixture | `docs/demonstration_fixture/` | ✅ |
| Double-counting fixture | `docs/demonstration_fixture_double_counting/` | ✅ |
| Problem statement | `PROBLEM_STATEMENT.md` | ✅ |
| Security policy | `SECURITY.md` | ✅ |
| Changelog | `CHANGELOG.md` | ✅ |
| Server config | `server.json` | ✅ |
| App config | `app.yaml` | ✅ |
| Presentation | `docs/presentation/slides.md` | ✅ |
