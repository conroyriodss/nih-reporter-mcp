# NIH RePORTER MCP Server
## GSA MCP Server and AI Agent Government Hackathon

**Rich Conroy** — NIH/OD/ODSS (conroyri@nih.gov) 
October 2026

---

<!-- Slide 1: Problem Statement -->

## The Problem

### NIH funds ~$47.5B/year in research. Answering basic questions about it is surprisingly hard.

- **"How much has NIH spent on CRISPR gene editing?"** — No single query gives the right answer. The RePORTER API has a 10,000-record ceiling, multi-component awards create double-counted records, and official spending categories diverge from keyword searches.

- **"Is an investigator's work overlapping?"** — The old approach capped results at 100 records per query, silently missing awards for prolific investigators.

- **Two audiences, one data source**: Congressional oversight staff need trustworthy totals. Researchers need discoverable grants. Both use the same underlying API, but its raw output requires expert interpretation.

**Core challenge:** Wrapping a government API 1:1 doesn't solve the problem — it replicates the problem at a different layer. Wrong answers feel more dangerous when delivered with AI confidence.

---

<!-- Slide 2: Solution Overview -->

## Solution: Goal-Oriented MCP Server

### 14 tools, each designed around a user goal — not an API endpoint

| Category | Tools | Key capability |
|---|---|---|
| **Funding analysis** | `summarize_funding_by_topic`, `funding_trend_by_year`, `organization_funding_profile` | Full pagination (up to 10,000 records), subproject deduplication, honest completeness flagging |
| **Project discovery** | `search_funded_projects`, `get_project_by_id`, `search_recent_awards` | Filtered search with fiscal year, state, agency, sort-by-award; server-side `group_by` faceting for deduped award counts |
| **Investigator tools** | `investigator_portfolio`, `check_investigator_overlap` | Full pagination (no 100-record cap), explicit project exclusion for Other Support review |
| **Peer review** | `funded_projects_by_study_section` | Study section distribution of funded projects |
| **Publications** | `list_publications_for_project`, `get_publication_details` | PubMed linkage via NCBI E-utilities |
| **Clinical trials** | `clinical_trials_lookup` | ClinicalTrials.gov v2: grant-linked trials, evidence-class classification, NIH-vs-FDA disambiguation |
| **Audit & transparency** | `export_evidence_bundle` | Source record IDs, query criteria, reproduction steps |
| **Health context** | `explain_health_topic` | MedlinePlus plain-language explanations (EN/ES) |

**Plus:** 9 prompts across 3 audiences (analyst, program officer, citizen scientist), 3 resources (server_info, response_guidelines, spending_categories), and a Databricks-hosted web app.

---

<!-- Slide 3: Technical Approach and Key Decisions -->

## Technical Approach

### Architecture

```
AI Agent (any model) → MCP Protocol → NIH RePORTER MCP Server
                                           │
                                     ┌─────┴─────┐
                                     │ 14 Tools  │
                                      │ 9 Prompts │
                                      │ 3 Resources│
                                      └─────┬─────┘
                                            │
                      ┌────────┼────────┼─────────┐
                      │        │        │         │
               RePORTER API  NCBI   MedlinePlus  ClinicalTrials.gov
```

### Key Decision 1: Deduplication over naive summation

Naively summing all RePORTER award amounts overstates CRISPR FY2023 funding by **10.1%**:

| Method | Total | Why |
|---|---|---|
| All records (naive sum) | $921,543,173 | Includes parent + child records |
| Whole award (deduplicated) | $836,981,580 | Excludes 226 subproject records |
| **Overstatement** | **$84,561,593 (10.1%)** | Silent if not caught |

### Key Decision 2: Honest completeness flagging

Every aggregation result includes `complete: true/false`, `total_matching`, and `projects_aggregated`. When the 10,000-record API ceiling truncates results, the tool says so — rather than silently reporting a partial total as if it were exact.

### Key Decision 3: Tool descriptions drive agent behavior

A single docstring edit to `search_funded_projects` dramatically reduced redundant tool calls: BC-1 (competitive renewal %) dropped from 32 calls to 1; BC-2 (top institution) dropped from 18 calls to 1 (real agent traces, `databricks-claude-sonnet-4-5`, v0.14.0). Multi-model eval confirms: descriptions clear enough for one model family work for all three tested (92% across GPT, Claude, Llama).

**Note on `group_by` faceting:** `search_funded_projects` with `group_by='application_type'` uses server-side faceting with `exclude_subprojects=True`, returning **deduped award counts** directly from the API. This path is not subject to the 10,000-record pagination ceiling — it returns exact bucket counts regardless of cohort size (e.g., 29,560 R01 awards in FY2020, 9 buckets, sum = total, 0 remainder).

### Key Decision 4: Full pagination for overlap checking

Upgraded `check_investigator_overlap` from a single 100-record API call to full `paginate_all()`. Proven: Francis Collins has 102 records — the old implementation silently missed 2.

---

<!-- Slide 4: Demonstration of Functionality -->

## Demonstration

### Live results (A5 batch 2026-10-19 at v0.13.0, re-confirmed at v0.14.0)

**Q: "How much has NIH spent on CRISPR gene editing?"**

```
CRISPR gene editing FY2023:
  1,739 matching projects, 1,506 aggregated (226 subprojects excluded)
  $836,981,580 (whole_award, complete=True)
  records_with_missing_amount: 7, deduped_count: 0
  note: flags the 7 missing amounts and the orphan subprojects
        (no "Total is exact" statement)
```

**Q: "What are the five biggest Alzheimer's biomarker grants in Massachusetts in FY2024?"**

| Rank | Award record | Institution | Award |
|---|---|---|---|
| 1 | U19AG068753 | Boston University | $5,130,473 |
| 2 | U19AG073172 | Boston University | $4,696,857 |
| 3 | U19AG073172, core component record | Boston University | $2,767,350 |
| 4 | RF1AG083764 | Brigham and Women's | $2,451,933 |
| 5 | R01AG082046 | Boston University | $2,320,702 |

*The five largest matching **award records** (85 matching projects; single round-trip tool call). These are records, not five distinct awards: rank 3 is a component record of the rank-2 U19AG073172 award, so the five rows cover four distinct awards.*

### Test Results Summary

| Tier | Result |
|---|---|
| Model-free CI (pytest) | 155 passed + 2 xfail (6 CI targets: 5 unit files + robustness Part C, no network) |
| Live-server smoke tests | 17/17 passed |
| Live robustness (server-req) | 38 (32 stable + 6 pass-with-retry); transient upstream timeout. Part C's 11 mocked tests are in the 155 above |
| Live correctness (ground truth) | 8/8 passed against independently-derived values |
| Multi-model tool selection | 22/24 correct (92%) across GPT-5-5, Claude Sonnet 4-6, Llama 3.3 70B (re-verified 2026-10-20) |
| Tool-selection determinism | 3/3 stable (5 repeats each, re-verified) |
| Argument validity | 24/24 (100%, re-verified) |
| CRISPR sickle cell FY2024 fixture | $19,790,134.00 — exact match (A4 re-verified 2026-10-19) |

### Known Limitations (honestly documented)

- Topic-search orphan subprojects: CRISPR-mentioning subprojects of non-CRISPR umbrella grants are excluded and flagged in the returned `note` (166 orphans for CRISPR FY2023). Exactness is reported through `complete`, `records_with_missing_amount` and `note`; `is_exact` is an internal aggregator property, not a returned field
- 10,000-record API ceiling → flagged via `complete=False`
- Substring org-name matching upstream → tool defaults to exact match
- 38 of ~300 RCDC spending categories covered; others need numeric ID
- 1 stub tool remaining (USAspending.gov cross-agency comparison) → documented in roadmap. ClinicalTrials.gov is now **implemented and registered** (`clinical_trials_lookup`, 23 offline tests)

---

<!-- Slide 5: Repository and Artifacts -->

## Repository Structure

```
nih-reporter-mcp/
├── src/nih_reporter_mcp/     14 tools, 9 prompts, 3 resources
├── tests/                   7 test files, 203 tests
│   ├── test_counting.py       69 tests (67p + 2xf)
│   ├── test_security.py       24 tests
│   ├── test_prompt_contracts.py 29 tests
│   ├── test_clinical_trials.py 23 tests
│   ├── test_version_contract.py 1 test (/version == live registries)
│   ├── test_correctness.py    8 tests (live server)
│   └── test_robustness.py     49 tests (11 mocked + 38 live)
├── eval/smoke_tests.py       17 assertions (standalone; t9 LLM-only in notebook)
├── docs/                     8 documents + 2 fixture dirs
├── .github/workflows/ci.yml  Python 3.11 + 3.12
├── notebook-merged           37-cell Databricks notebook
└── Deployed app: mcp-nih-reporter.aws.databricksapps.com
```

**GitHub:** `github.com/conroyriodss/nih-reporter-mcp` (public) 
**License:** MIT | **Security:** See `SECURITY.md`
