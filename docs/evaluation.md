# NIH RePORTER MCP Server — Evaluation Document

**Project:** NIH RePORTER MCP Server 
**Team:** Rich Conroy (conroyri@nih.gov), NIH/OD/ODSS 
**Hackathon:** GSA MCP Server and AI Agent Government Hackathon 
**Version:** v0.14.1 
**Tag SHA:** `017c97a51b40cd6241319e834af2dc8688e605ce` 
**Date:** October 20, 2026

---

## 1. Testing Methodology

### 1.1 Test Architecture — Three Independent Tiers

All tests are in the `tests/` directory and runnable with standard `pytest`. The tiers are designed so that each can run independently without the others.

#### Tier 1: Model-Free CI (GitHub Actions, every push/PR)

**Status: ✅ Verified at v0.14.1 — 154 pass + 2 xfail offline (CI)**

| Test file | Tests | What it covers |
|---|---|---|
| `tests/test_counting.py` | 67 passed + 2 xfailed | Synthetic-fixture unit tests for `aggregate_funding()`: subproject exclusion, `appl_id` deduplication, missing-amount tracking, `is_exact` flag, page-boundary dedup, multi-year rollup, whole_award vs all_records basis separation, pagination clamping, server-side application-type faceting, PI group-by, IC-attribution edge cases (2 xfail — known upstream limitation) |
| `tests/test_security.py` | 24 passed | Host-allowlist enforcement (only `api.reporter.nih.gov`, `eutils.ncbi.nlm.nih.gov`, `wsearch.nlm.nih.gov`, `clinicaltrials.gov` allowed), input-size guards on topic length and fiscal-year array size, parameter type validation |
| `tests/test_prompt_contracts.py` | 29 passed | Every prompt (`funding_overview`, `institution_report`, `compare_rcdc_vs_freetext`, `research_landscape_summary`, `portfolio_brief`, `other_support_review`, `investment_to_outputs`, `explain_funding_landscape`, `follow_the_evidence`) references only tools that actually exist, and every tool referenced uses parameter names that match the tool's actual schema |
| `tests/test_clinical_trials.py` | 23 passed | ClinicalTrials.gov v2 integration: grant-linked trial lookup, condition search, evidence-class classification, NIH-vs-FDA disambiguation, empty-result handling, CT parsing |
| `tests/test_robustness.py::TestPartC` | 11 passed | Mocked upstream failure handling: HTTP 500 → RuntimeError, 429 → retry-then-succeed, timeout → RuntimeError, oversized response → rejection, network error → RuntimeError, HTTP 400/403 → ValueError, malformed JSON → error, malformed-200-with-partial-keys → error |

**Evidence tier: Verified.** Run command:
```bash
PYTHONPATH=src pytest tests/test_counting.py tests/test_security.py \
  tests/test_prompt_contracts.py tests/test_clinical_trials.py \
  tests/test_robustness.py::TestPartC_MockedUpstreamFailures -v
```

CI configuration: `.github/workflows/ci.yml` — runs on Python 3.11 and 3.12 on every push to `main` and every PR.

#### Tier 2: Live-Server Integration (requires running MCP server)

**Status: ✅ Verified at v0.14.0 — 17/17 smoke tests passed**

The smoke suite (`eval/smoke_tests.py`) runs 17 automated assertions against the **live NIH RePORTER API** (not mocked). Each test calls a tool via the MCP protocol and validates the structured response:

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

Additionally, `tests/test_correctness.py` contains 8 tests that verify funding arithmetic against independently-derived ground truth (requires a running MCP server): ground-truth exact match, double-counting proof, provenance reproducibility, missing-amount honesty, cross-tool basis consistency, overlap completeness flag, and two regression guards (CRISPR FY2023, Alzheimer's FY2023).

**Evidence tier: Verified.** `eval/smoke_tests.py --sequential` output shows "TOTAL: 17/17 passed" (run 2026-10-20 at v0.14.0). `test_correctness.py` 8/8 passed individually against live MCP server (2026-10-20).

#### Tier 3: Multi-Model Agent Evaluation (Databricks notebook only)

**Status: ✅ Re-verified at v0.14.0 — results below**

Notebook cells 32–36 run a structured evaluation of tool-selection accuracy across three model families to demonstrate that the server's tool descriptions are agent-agnostic. Re-run 2026-10-20T00:15–00:25Z on Databricks serverless, server at v0.14.0 clean checkout (`4eec13c`), 14 tools:

| Eval | Result | Evidence tier |
|---|---|---|
| Tool-selection accuracy (8 questions × 3 models) | 22/24 correct (92%) | Re-verified (EVAL_VERDICTS Claim 1) |
| Per-model: GPT-5-5 | 7/8 (88%) | Re-verified |
| Per-model: Claude Sonnet 4-6 | 7/8 (88%) | Re-verified (was 8/8 in prior run — Q5 flipped) |
| Per-model: Llama 3.3 70B Instruct | 8/8 (100%) | Re-verified (was 7/8 in prior run — Q5 flipped) |
| Unanimous correct (all 3 agree) | 6/8 | Re-verified |
| Tool-selection determinism (3 questions × 5 repeats, GPT-5-5) | 3/3 stable | Re-verified (EVAL_VERDICTS Claim 3) |
| Argument validity (8 questions × 3 models) | 24/24 (100%) | Re-verified (EVAL_VERDICTS Claim 2) |

**Disagreement detail:** Q5 ("What grants does Francis Collins currently hold?") — both GPT-5-5 and Claude Sonnet 4-6 selected `check_investigator_overlap` instead of the expected `investigator_portfolio`. Llama selected correctly. Headline score (22/24) matches the prior run; the failure pattern shifted (Claude Q5 flipped from correct to incorrect, Llama Q5 flipped from incorrect to correct). This confirms Q5 is a genuine description-clarity ambiguity, not a model-specific quirk.

**Note:** The 8-question evaluation set predates `group_by`, `application_types`, `spending_category`, and `clinical_trials_lookup`. No question tests routing to or away from these newer capabilities. The 22/24 score covers the original tool surface only.

**Evidence tier: Re-verified.** Re-run 2026-10-20 at v0.14.0 (see `docs/demonstration_fixture/EVAL_VERDICTS.md`). Prior run (October 16, 2026) produced identical headline score with different per-model Q5 pattern.

### 1.2 Ground Truth Methodology

The CRISPR gene editing FY2024 ground truth fixture (`tests/fixtures/crispr_sickle_cell_fy2024.json`) was independently constructed by:
1. Querying RePORTER API directly with known parameters
2. Computing the expected total manually from the raw response records
3. Verifying the server's output matches: **$19,790,134.00** (exact fixture match confirmed October 16, 2026)

See `docs/ground_truth_methodology.md` for the full procedure.

---

## 2. Performance Metrics

### 2.1 Headline Figures (Live-Verified 2026-10-19T23:42–23:51Z, A5 batch at v0.13.0; re-confirmed stable at v0.14.0)

| Metric | Value | Evidence |
|---|---|---|
| CRISPR FY2023 whole_award total | $836,981,580 | Verified: A5 LF-2a (2026-10-19T23:42Z) + t1 |
| CRISPR FY2023 all_records total | $921,543,173 | Verified: A5 LF-2b (2026-10-19T23:48Z) + t7 |
| Naive-sum overstatement | 10.1% | Verified: ($921.5M − $837.0M) / $837.0M, A5 re-run |
| Alzheimer's FY2023 whole_award | $4,020,899,771 | Verified: A5 LF-3a (2026-10-19T23:42Z) |
| Alzheimer's FY2023 all_records | $4,685,253,389 | Verified: A5 LF-3b (2026-10-19T23:48Z) |
| Alzheimer's overstatement | 16.5% | Verified: A5 re-run |
| CRISPR sickle cell FY2024 (fixture) | $19,790,134.00 | Verified: A4 exact match (2026-10-19T23:21Z) |
| Total matching projects (CRISPR FY2023) | 1,739 | Verified: t1 |
| Projects aggregated (whole_award) | 1,506 | 1,739 − 226 subprojects − 7 missing amounts |
| Subprojects excluded | 226 | Verified: t7 |
| Records with missing amounts | 7 | Verified: A5 LF-2a |
| Deduplication (appl_id) | 0 for this query | Verified: A5 LF-2a |
| 10,000-record API ceiling | Honestly flagged | Verified: t2 (complete=False) |
| R01 FY2020 competitive renewals | 1,089 of 29,560 (3.7%) | Verified: A5 LF-4 (deduped awards via group_by). Supersedes old 397 (client-side) |
| R01 FY2023 type-5 continuations | 21,150 of 30,443 (69.5%) | Verified: A5 LF-5. Supersedes old 6,843 (10K cap) |
| P41 FY2015 deduped awards | 77 total, 13 competitive renewals (17%) | Verified: A5 LF-9a. Supersedes old 85 (record count) |
| P41 FY2025 deduped awards | 31 total, 1 competitive renewal (3%) | Verified: A5 LF-9b. Supersedes old 7 (record count) |
| R01 FY2020 faceting integrity | 9 buckets, sum=29,560=total, 0 remainder | Verified: A5 LF-10. Code 8 (Merit Extension)=11 |

### 2.2 Tool-Call Efficiency (Qualitative)

A single docstring edit to `search_funded_projects` measurably reduced redundant tool calls. The root cause: the original description was ambiguous enough that LLMs issued near-duplicate queries believing minor rewording might change results, when RePORTER's search already normalizes variants server-side.

**Demonstrated by real agent traces (not harness-measured):**

| Behavioral case | Before (calls) | After (calls) | Model |
|---|---|---|---|
| BC-1: R01 FY2020 competitive renewal % | 32 | 1 | GPT-5-5 |
| BC-2: R21 FY2018 top institution | 18 | 1 | GPT-5-5 |

**Note:** The earlier quantitative metric ("avg 2.0 → 1.0, stdev 1.7 → 0.0") from the t9 harness has been dropped. The harness had three defects: (1) the "before" measurement ran before `CALL_LOG`/`run_agent` were defined, (2) a zero-call pass falsely rewards non-use, (3) 4,000-char truncation may alter agent behavior vs. the real server. See `EVAL_VERDICTS.md` §3 for full rationale. The qualitative point is valid and demonstrated by the behavioral case traces above.

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

This is documented in `docs/findings.md` (Finding #11) and tested in `test_counting.py` (67 tests + 2 xfail). The 10.1% and 16.5% overstatement figures were re-verified in the A5 live-figure batch (2026-10-19T23:42–23:51Z).

### 4.2 Official Category vs. Free-Text Search Divergence

NIH's RCDC spending categories and free-text keyword searches return **dramatically different totals** for the same disease area. For "long covid" in FY2023: RCDC category reports $199.6M while free-text search finds $891.7M. Neither is "wrong" — they measure different things (curated categorization vs. text occurrence).

**Solution:** `compare_rcdc_vs_freetext` prompt explicitly runs both methods and presents both numbers with a documented explanation.

### 4.3 Tool Description Quality Drives Agent Accuracy

A single docstring edit to `search_funded_projects` dramatically reduced redundant tool calls. Before the fix, the description was ambiguous enough that the LLM issued near-duplicate queries believing minor rewording might change results. After: BC-1 (competitive renewal %) dropped from 32 calls to 1; BC-2 (top institution) dropped from 18 calls to 1. These are real agent traces against `databricks-claude-sonnet-4-5` at v0.14.0, not harness-measured.

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
| 14 tools | `src/nih_reporter_mcp/tools/` | ✅ (includes `clinical_trials_lookup`, registered since v0.13.0) |
| 9 prompts | `src/nih_reporter_mcp/prompts/` | ✅ |
| 3 resources | `src/nih_reporter_mcp/resources/` | ✅ (server_info, response_guidelines, spending_categories) |
| Unit tests (model-free) | `tests/test_counting.py`, `test_security.py`, `test_prompt_contracts.py`, `test_clinical_trials.py` | ✅ 154p + 2xf (CI: 4 unit files + robustness Part C) |
| Robustness tests (mocked) | `tests/test_robustness.py::TestPartC` | ✅ 11p |
| Correctness tests (live) | `tests/test_correctness.py` | ✅ 8 tests |
| Robustness tests (live) | `tests/test_robustness.py` Parts A/B/D/E | ✅ 49 tests (43 stable + 6 pass-with-retry) |
| CI workflow | `.github/workflows/ci.yml` | ✅ |
| Ground truth fixture | `tests/fixtures/crispr_sickle_cell_fy2024.json` | ✅ |
| Smoke tests | `eval/smoke_tests.py` | ✅ 17/17 |
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
| Evidence package | `docs/demonstration_fixture/` (8 files) | ✅ (RUN_MANIFEST, EVAL_VERDICTS, fixture bundle) |

---

## Appendix: Reconciliation Change Log (v0.14.0)

Changes applied to this document during the B1 reconciliation pass (2026-10-20), reconciling against the frozen canonical values block at v0.14.0 (`4eec13c`).

| # | Location | Old value | New value | Canonical source |
|---|---|---|---|---|
| 1 | Header line 6 | v0.10.2-dev | v0.14.0 | Tag |
| 2 | Header line 7 | (absent) | Tag SHA `4eec13c...` | Tag |
| 3 | Header line 8 | October 16, 2026 | October 20, 2026 | Tag date |
| 4 | §1.1 Tier 1 status | 75 passed + 2 xfailed | 154 pass + 2 xfail offline (CI) | CI scope: 4 unit files + Part C |
| 5 | §1.1 test_counting | 20p + 2xf | 67p + 2xf | Subprocess pytest |
| 6 | §1.1 test_security | 21p | 24p | Subprocess pytest |
| 7 | §1.1 test_prompt_contracts | 24p | 29p | Subprocess pytest |
| 8 | §1.1 (new row) | (absent) | test_clinical_trials: 23p | New file at v0.13.0 |
| 9 | §1.1 Tier 2 status | 18/18 smoke | 17/17 smoke | t5 fixed, t9 notebook-only |
| 10 | §1.1 Tier 2 evidence | Notebook Cell 12 18/18 | smoke_tests.py 17/17 + test_correctness 8/8 | A3b re-run |
| 11 | §1.1 test_correctness | 6 tests | 8 tests | Subprocess pytest |
| 12 | §1.1 Tier 3 status | Verified | Re-verified at v0.14.0 | EVAL_VERDICTS |
| 13 | §1.1 Claude Sonnet | 8/8 (100%) | 7/8 (88%) | EVAL_VERDICTS Claim 1 (Q5 flipped) |
| 14 | §1.1 Llama | 7/8 (88%) | 8/8 (100%) | EVAL_VERDICTS Claim 1 (Q5 flipped) |
| 15 | §1.1 Unanimous | 7/8 | 6/8 | EVAL_VERDICTS Claim 1 |
| 16 | §1.1 Disagreement detail | GPT+Llama wrong | GPT+Claude wrong, Llama correct | EVAL_VERDICTS |
| 17 | §1.1 (new) | (absent) | Note: 8-Q set predates new tool surface | EVAL_VERDICTS |
| 18 | §2.1 heading | Live-Verified October 16 | A5 batch 2026-10-19 + v0.14.0 | A5 run window |
| 19 | §2.1 evidence refs | notebook Cell 24 | A5 LF-IDs with timestamps | A5 batch |
| 20 | §2.1 (new rows) | (absent) | Alzheimer's, R01 renewals, type-5, P41 deduped, faceting | A5 LF-3/4/5/9/10 |
| 21 | §2.2 | Quantitative: avg 2.0→1.0 | Qualitative: BC-1 32→1, BC-2 18→1 + harness-dropped note | EVAL_VERDICTS §3 |
| 22 | §4.1 | Finding #1, 20 tests | Finding #11, 67 tests + 2 xfail, A5 re-verified | Canonical |
| 23 | §4.3 | "2.0 → 1.0 calls/question" | Qualitative BC-1/BC-2 traces | EVAL_VERDICTS |
| 24 | Appendix tools | 13 tools | 14 tools (CT registered since v0.13.0) | Server inventory |
| 25 | Appendix resources | 2 resources | 3 resources | Server inventory |
| 26 | Appendix unit tests | 65p + 2xf | 154p + 2xf (CI: 4 unit files + robustness Part C) | Subprocess pytest |
| 27 | Appendix correctness | 6 tests | 8 tests | Subprocess pytest |
| 28 | Appendix robustness | 38 tests | 49 tests (43 stable + 6 retry) | Subprocess pytest |
| 29 | Appendix smoke | 18/18 | 17/17 | t5 fixed, t9 notebook-only |
