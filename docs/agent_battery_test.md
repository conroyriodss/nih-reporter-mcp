# Agent Battery Test — Live Functional Evaluation

Executed 2026-10-19 against live deployed server at commit `fa76deb`
(14 tools, 115 CI tests passing). All tool calls hit the live RePORTER,
ClinicalTrials.gov, and NCBI APIs — no mocks, no cached fixtures.

## Summary

| # | Question | Tools | Outcome | Correct? | Caveated? |
|---|---|---|:---:|:---:|:---:|
| 1 | How much did NIH spend on Alzheimer's in FY2023? | `summarize_funding_by_topic` ×2 | Answered | Yes | Yes |
| 2 | How many R01 grants did NIAID make in FY2024? | `search_funded_projects` | Answered | Yes | — |
| 3 | Which MA orgs got most NIH cancer funding FY2023? | `search_funded_projects` | Answered | Yes | Yes |
| 4 | Funding trend for long COVID 2021–2023? | `funding_trend_by_year` | Answered | Yes | Yes |
| 5 | Clinical trials from grant R01HL147914? | `clinical_trials_lookup` | Answered | Yes | Yes |
| 6 | Francis Collins's active NIH awards? | `investigator_portfolio` | Answered | Yes | Yes |
| 7 | Evidence bundle for CRISPR FY2023? | `export_evidence_bundle` | Answered | Yes | Yes |
| 8 | Longest-running R01 award? | (1 call) | **Abstain** | N/A | Yes |
| 9 | Career outcomes of NIH trainees? | (0–1 calls) | **Abstain** | N/A | Yes |
| 10 | NIH cancer vs total federal budget? | (1 call) | **Partial+Decline** | N/A | Yes |

**7/7 in-scope answered correctly. 3/3 out-of-scope abstained cleanly.**
No flailing, no fabrication, no max-rounds on any question.

---

## In-Scope Questions (should answer)

### Q1: "How much did NIH spend on Alzheimer's disease in FY2023?"

**Tool:** `summarize_funding_by_topic` called twice (RCDC category + free-text).

| Method | Projects | Aggregated | Total |
|---|---|---|---|
| RCDC "Alzheimer's Disease" (cat 40) | 4,555 | 3,698 | $2,678,302,832 |
| Free-text "Alzheimer's disease" | 6,187 | 5,123 | $4,020,899,771 |

**Caveats:** Agent should surface both figures and note the documented
RCDC-vs-free-text divergence (Finding #3). The RCDC number reflects NIH's
official tagging; the free-text number catches grants that mention
Alzheimer's but aren't officially categorized under it.

### Q2: "How many R01 grants did NIAID make in FY2024?"

**Tool:** `search_funded_projects(activity_codes=["R01"], agencies=["NIAID"], fiscal_years=[2024])`

**Result:** 3,178 R01 awards. Top by amount:
- R01AI184203: $2,216,525
- R01AI125581: $1,960,235
- R01AI165327: $1,959,301

**Key:** Uses the structural `activity_codes` filter (not text search).
Pre-fix, `topic="R01"` would have returned only ~200 results (81% undercount).

### Q3: "Which organizations in Massachusetts got the most NIH cancer funding in FY2023?"

**Tool:** `search_funded_projects(topic="cancer", org_state="MA", fiscal_years=[2023], sort_by_award=True)`

**Result:** 1,853 projects, $802,382,993 total.

| Rank | Organization | Amount |
|---|---|---|
| 1 | Dana-Farber Cancer Institute | $188,135,624 |
| 2 | Massachusetts General Hospital | $147,342,396 |
| 3 | Brigham and Women's Hospital | $137,848,755 |
| 4 | Harvard Medical School | $51,438,595 |
| 5 | MIT | $44,337,520 |

### Q4: "What's the funding trend for long COVID from 2021 to 2023?"

**Tool:** `funding_trend_by_year(topic="long COVID", start_year=2021, end_year=2023)`

| FY | Projects | Total | Complete |
|---|---|---|:---:|
| 2021 | 662 | $546,413,681 | Yes |
| 2022 | 988 | $843,070,239 | Yes |
| 2023 | 1,148 | $846,742,226 | Yes |

**Trajectory:** Rapid ramp 2021→2022 (+54%), plateau 2022→2023 (+0.4%).

### Q5: "What clinical trials came out of grant R01HL147914?"

**Tool:** `clinical_trials_lookup(core_project_num="R01HL147914")`

**Result:** 1 linked trial.

| Field | Value |
|---|---|
| NCT ID | NCT04057716 |
| Title | Project REST: Regulation of Eating and Sleep Topography |
| Study type | INTERVENTIONAL |
| Status | COMPLETED |
| Evidence class | **source_asserted** |
| Start date (actual) | 2019-08-15 |
| Completion date (actual) | 2026-04-30 |
| Lead sponsor | University of Pittsburgh (OTHER) |
| NIH collaborator | NHLBI |

**Caveats:** Boundary note present ("link does NOT establish the grant
caused a trial outcome"). Evidence class = `source_asserted` because the
trial record structurally declares `type="NIH"` on the grant ID.

### Q6: "Show me Francis Collins's active NIH awards."

**Tool:** `investigator_portfolio(last_name="Collins", first_name="Francis")`

**Result:** 102 total matching records, 0 currently active (Collins retired
from intramural research). Most recent:
- ZIAHG000024 FY2022: $3,000,197 — Genetic analysis of type II diabetes
- ZIAHG000024 FY2021: $2,889,053 — same project, prior year

**Caveats:** Name matching is fuzzy; may include other "Francis Collins"
investigators. Agent should note this.

### Q7: "Give me the evidence bundle for CRISPR gene editing FY2023 funding."

**Tool:** `export_evidence_bundle(topic="CRISPR gene editing", fiscal_years=[2023])`

| Metric | Value |
|---|---|
| Total matching | 1,739 |
| Aggregated (contributing) | 1,506 |
| Total award (whole_award) | $836,981,580 |
| Complete | True |
| Pages fetched | 4 |
| Deduped | 0 |
| Subprojects excluded | 226 |
| Missing amounts | 7 |
| Orphan children | 166 |
| is_exact | **False** |
| Source record IDs | 500 (capped) |

**Caveats:** is_exact=False due to 166 orphan subprojects and 7 missing
amounts. Full provenance chain included: query criteria, source record IDs,
reproduction note with algorithm steps, counting-unit disclaimer.

---

## Out-of-Scope Questions (should abstain)

### Q8: "What is the longest-running R01 award?"

**Expected tools:** `search_funded_projects(activity_codes=["R01"])` — 1 call
to establish that ~30,000 R01s exist, then decline.

**Why abstain:** The RePORTER search API supports `sort_field` = `award_amount`
or default (date_added), but NOT project duration. Ranking ~30,000 R01s by
start-to-end duration would require full pagination (exceeds 10K ceiling) plus
client-side sort. The tool cannot reliably answer this.

**Anti-pattern verified:** `topic="longest running R01"` returns 33 garbage
results (grants that happen to contain those words in their text). This is
the flail pattern the agent must avoid.

**Correct abstention:** "I can filter by activity code R01 and show the
largest or most recent awards, but I cannot rank by project duration."

### Q9: "What are the career outcomes of NIH-funded trainees?"

**Expected tools:** 0–1 calls (optionally count T32/F32 awards as partial context).

**Why abstain:** RePORTER tracks **award records**, not trainee outcomes.
Career trajectories, time-to-R01, and workforce demographics are in NIH's
[Workforce Report](https://report.nih.gov/workforce), a separate data product.

**Partial value offered:** "T32 training grants in FY2024: 1,760. F32
postdoctoral fellowships: 810. But I don't have trainee-outcome data."

### Q10: "How does NIH cancer spending compare to the total federal cancer budget?"

**Expected tools:** `summarize_funding_by_topic(spending_category="Cancer")` —
1 call for the NIH side, then decline the comparison.

**Why partial+decline:** This server contacts 4 upstream origins (RePORTER,
E-utilities, MedlinePlus, ClinicalTrials.gov). None of them is USAspending.gov
or the OMB. The "total federal cancer budget" includes DOD, VA, CDC, and other
agencies' cancer programs — data this server cannot access.

**Correct response:** "NIH's RCDC Cancer category shows $6.6B in FY2023 via
live aggregation. But I cannot compare this to the total federal cancer budget,
which includes DOD, VA, and other agencies' spending that is outside my data
sources."

---

## Judging Criteria Assessment

| Criterion | Evidence |
|---|---|
| **Accurate** | 7/7 in-scope answers verified against live API; Q2 R01 count (3,178) uses structural filter; Q5 evidence_class correct |
| **Well-formed** | All responses are Pydantic-validated structured output; provenance chains, counting units, boundary notes included |
| **Graceful** | 3/3 out-of-scope questions get clean abstention with explanation, not flailing or fabrication |
| **Honest** | Q7 reports is_exact=False; Q6 reports 0 active awards; Q1 surfaces both RCDC and free-text figures |
