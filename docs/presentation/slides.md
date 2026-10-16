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

### 13 tools, each designed around a user goal — not an API endpoint

| Category | Tools | Key capability |
|---|---|---|
| **Funding analysis** | `summarize_funding_by_topic`, `funding_trend_by_year`, `organization_funding_profile` | Full pagination (up to 10,000 records), subproject deduplication, honest completeness flagging |
| **Project discovery** | `search_funded_projects`, `get_project_by_id`, `search_recent_awards` | Filtered search with fiscal year, state, agency, sort-by-award |
| **Investigator tools** | `investigator_portfolio`, `check_investigator_overlap` | Full pagination (no 100-record cap), explicit project exclusion for Other Support review |
| **Peer review** | `funded_projects_by_study_section` | Study section distribution of funded projects |
| **Publications** | `list_publications_for_project`, `get_publication_details` | PubMed linkage via NCBI E-utilities |
| **Audit & transparency** | `export_evidence_bundle` | Source record IDs, query criteria, reproduction steps |
| **Health context** | `explain_health_topic` | MedlinePlus plain-language explanations (EN/ES) |

**Plus:** 9 prompts across 3 audiences (analyst, program officer, citizen scientist), 2 resources, and a Databricks-hosted web app.

---

<!-- Slide 3: Technical Approach and Key Decisions -->

## Technical Approach

### Architecture

```
AI Agent (any model) → MCP Protocol → NIH RePORTER MCP Server
                                           │
                                     ┌─────┴─────┐
                                     │ 13 Tools  │
                                     │ 9 Prompts │
                                     │ 2 Resources│
                                     └─────┬─────┘
                                           │
                          ┌─────────────┼────────────┐
                          │              │             │
                   RePORTER API    NCBI E-utils  MedlinePlus
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

A single docstring edit to `search_funded_projects` reduced average tool calls per question from **2.0 to 1.0** (model held constant). Multi-model eval confirms: descriptions clear enough for one model family work for all three tested.

### Key Decision 4: Full pagination for overlap checking

Upgraded `check_investigator_overlap` from a single 100-record API call to full `paginate_all()`. Proven: Francis Collins has 102 records — the old implementation silently missed 2.

---

<!-- Slide 4: Demonstration of Functionality -->

## Demonstration

### Live results from October 16, 2026 notebook run

**Q: "How much has NIH spent on CRISPR gene editing?"**

```
CRISPR gene editing FY2023:
  1,739 matching projects, 1,506 aggregated (226 subprojects excluded)
  $836,981,580 (whole_award, complete=True)
  7 records with missing amounts, 0 deduped
  is_exact: False (7 missing amounts)
```

**Q: "What are the five biggest Alzheimer's biomarker grants in Massachusetts in FY2024?"**

| Rank | Project | Institution | Award |
|---|---|---|---|
| 1 | U19AG068753 | Boston University | $5,130,473 |
| 2 | U19AG073172 | Boston University | $4,696,857 |
| 3 | U19AG073172 (core) | Boston University | $2,767,350 |
| 4 | RF1AG083764 | Brigham and Women's | $2,451,933 |
| 5 | R01AG082046 | Boston University | $2,320,702 |

*85 matching projects; tool-call efficiency: 1.0 calls (single round-trip)*

### Test Results Summary

| Tier | Result |
|---|---|
| Model-free CI (pytest) | 75 passed + 2 xfailed |
| Live-server smoke tests | 18/18 passed |
| Multi-model tool selection | 22/24 correct (92%) across GPT-5-5, Claude Sonnet 4-6, Llama 3.3 70B |
| Tool-selection determinism | 3/3 stable (5 repeats each) |
| Argument validity | 24/24 (100%) |
| CRISPR FY2024 fixture | $19,790,134.00 — exact match |

### Known Limitations (honestly documented)

- 10,000-record API ceiling → flagged via `complete=False`
- Substring org-name matching upstream → tool defaults to exact match
- 38 of ~300 RCDC spending categories covered; others need numeric ID
- 2 stub tools (ClinicalTrials.gov, USAspending.gov) → documented in roadmap

---

<!-- Slide 5: Repository and Artifacts -->

## Repository Structure

```
nih-reporter-mcp/
├── src/nih_reporter_mcp/     13 tools, 9 prompts, 2 resources
├── tests/                   5 test files, 121 test functions
│   ├── test_counting.py       22 tests (20p + 2xf)
│   ├── test_security.py       21 tests
│   ├── test_prompt_contracts.py 24 tests
│   ├── test_correctness.py    6 tests (live server)
│   └── test_robustness.py     48 tests (10 mocked + 38 live)
├── eval/smoke_tests.py       18 assertions
├── docs/                     8 documents + 2 fixture dirs
├── .github/workflows/ci.yml  Python 3.11 + 3.12
├── notebook-merged           37-cell Databricks notebook
└── Deployed app: mcp-nih-reporter.aws.databricksapps.com
```

**GitHub:** `github.com/conroyriodss/nih-reporter-mcp` (public) 
**License:** MIT | **Security:** See `SECURITY.md`
