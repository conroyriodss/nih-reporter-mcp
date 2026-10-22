<!-- Proposed seven-slide copy, including the cover. Speaker notes and source
references are not slide text. Submission identity is v0.14.6. Historical runs
retain their actual versions and dates. This rewrite does not report new CI,
live API, or model execution results. -->

<!-- Slide 1: Title -->

# NIH RePORTER MCP Server

## Inspectable NIH funding answers for AI agents

An answer includes its query, counting rules, source evidence, and limits.

Rich Conroy, NIH/OD/ODSS

GSA MCP Server and AI Agent Government Hackathon

Submission freeze: **v0.14.6**

<!-- Speaker notes
Opening: “An NIH funding answer should include enough evidence for someone else
to check the calculation. I will show a frozen cohort, reconcile its sum, and
show a question the agent should decline.”
Do not introduce the demo as a guarantee that every possible funding answer is
correct. The claim is inspectability and demonstrated behavior within scope.
-->

---

<!-- Slide 2: Problem statement -->

## A plausible funding answer can still mislead

- **Counting risk:** parent and component records can count the same funding twice.
- **Scope risk:** keyword matches can include projects outside an intended program or official spending category.
- **Missing-data risk:** a retrieval limit, absent amount, or missing relationship can look like a complete answer.

Program officers and the public need the cohort definition and evidence behind the number.

<!-- Speaker notes
Use “recorded award amounts” when describing the calculation. Do not silently
translate RePORTER award amounts into expenditures, lifetime grant value, or
the share attributable exclusively to a topic.

The previous deck's undated ~$47.5B/year opening invites a budget-year and scope
question without helping explain the product. The counting example on slide 5
provides direct evidence of the problem.

Sources: docs/findings.md, findings 11–13 and 18;
docs/demonstration_fixture/README.md;
docs/demonstration_fixture_double_counting/README.md.
-->

---

<!-- Slide 3: Solution overview -->

## Tools organized around analytical tasks

| User goal | Workflow |
|---|---|
| Define a funding portfolio | Select fiscal year and search method, then aggregate under explicit counting rules |
| Check a funding claim | Export query criteria, contributing IDs, and reproduction steps |
| Follow research outputs | Retrieve publication or trial associations with evidence limits |

**14 tools, 9 prompts, 3 resources**

MCP-compatible agents use RePORTER, NCBI, MedlinePlus, and ClinicalTrials.gov through the server.

<!-- Speaker notes
This is the goal-oriented design argument: a tool completes an analytical task
that otherwise requires multiple API requests and interpretation. Name
summarize_funding_by_topic and export_evidence_bundle rather than reading the
entire tool inventory.

The grant-to-output workflow retrieves reported associations. It does not
establish causality, funding-year attribution, or dollars allocated to a trial.
Investigator-overlap output identifies candidates for human review, not an
Other Support duplication determination. Funded-project distributions by study
section do not measure all review workload.

Sources: src/nih_reporter_mcp/tools/ (registered inventory);
docs/architecture.md; docs/roadmap.md.
-->

---

<!-- Slide 4: Demonstration of functionality -->

## One funding answer, reconciled record by record

**$19,790,134**

Frozen “CRISPR sickle cell” FY2024 keyword cohort

| Accounting step | Result |
|---|---:|
| Matching records | 38 |
| Excluded subproject | 1 |
| Contributing records | 37 |
| Raw-record sum, decision ledger, and stored tool total | $19,790,134 |

**`complete=true` describes retrieval. The excluded subproject's parent is absent, so associated award-family investment may be missing.**

<!-- Speaker notes
Demo sequence: open query.json, show the ledger and excluded record, show the
stored bundle total, then read its caveat aloud.

Exact search: advanced_text_search.operator="and", search_field="all",
search_text="CRISPR sickle cell", fiscal_years=[2024]. Funding basis:
whole_award. Deduplicate by appl_id, exclude non-null subproject_id, exclude null
award_amount, then sum. This snapshot has zero duplicate IDs and zero missing
amounts. The 37 contributing records represent 35 distinct core project
numbers, so do not describe them as 37 distinct grant families.

The excluded record is appl_id 10992993, subproject 9946 ("Project III",
sickle-cell iPSC work) of P50HD096723, $472,999. The keyword matched this child
but not its parent, a male-infertility genetics center whose abstract does not
match "CRISPR sickle cell". The cohort holds this one subproject, not the
center (five FY2024 subprojects, $1,711,713). Excluding it removes real
investment; it is not double-counting removal. Title, abstract and center
figures are Team-reported from RePORTER (2P50HD096723-06); the fixture stores
only appl_id, amount, core number, fiscal year and subproject ID. This fixture
demonstrates reproducible arithmetic and visible orphan exclusion. Slide 5
supplies the parent-plus-children proof.

Raw acquisition: 2026-10-15T20:31:43.117032+00:00. Stored tool response:
2026-10-18T19:07:59.647418+00:00. The repository reports a subsequent comparison
at v0.13.0 on October 19. Preserve those dates instead of relabeling them as a
new v0.14.6 execution.

All 37 contributing IDs are present in this small fixture. More generally,
source_record_ids lists up to 500 of N contributing IDs (capped for payload
size); records_aggregated gives the true count. Larger bundles require retained
raw records or a separate full ledger for record-by-record inspection.

Sources: docs/demonstration_fixture/query.json, raw_records.json,
raw_records.sha256, decision_ledger.csv, independent_total.md, tool_output.json.
-->

---

<!-- Slide 5: Technical approach and key decisions -->

## Counting rules change the answer

**U19AG068753, FY2024: one parent plus seven components**

| Calculation | Frozen result |
|---|---:|
| Sum all eight records | $10,260,946 |
| Whole-award total | $5,130,473 |

Application-ID deduplication and component exclusion address different errors. Missing amounts remain explicit.

Share of the FY2020 R01 funded cohort recorded as competitive renewals: **1,089 / 29,560 = 3.68%**, using the documented facet counting basis.

Facet counts do not supply the underlying funding records needed to reconcile dollar totals.

<!-- Speaker notes
The frozen family contains one parent with award_amount=$5,130,473 and seven
components whose amounts sum to $5,130,473. The all_records sum is exactly twice
the whole_award sum. Both raw hashes and ledger arithmetic are inspectable.

Do not describe all subprojects as duplicate application IDs. The whole_award
algorithm deduplicates application IDs and separately excludes component records.
It does not collapse every record sharing a core_project_num: distinct
application records, including additional funding actions, can legitimately
contribute.

R01 lookup documented in RUN_MANIFEST A5 LF-4/LF-10:
search_funded_projects(activity_codes=["R01"], fiscal_years=[2020],
group_by="application_type"). The documented result contains nine buckets,
sum=29,560 and zero remainder. Keep the stated counting basis. This percentage
is a share of the returned funded-award cohort, not a renewal success rate.
Bucket reconciliation does not establish universal facet completeness for all
possible queries, and it does not remove the 10,000-record retrieval limit for
funding arithmetic and full record-level provenance.

Backup figures from the submission materials:
- CRISPR FY2023: all_records $921,543,173; whole_award $836,981,580;
  difference $84,561,593, or 10.1% of whole_award.
- Alzheimer's FY2023: all_records $4,685,253,389; whole_award $4,020,899,771;
  difference $664,353,618, or 16.5% of whole_award.
Call these basis differences. CRISPR's documented 166 orphan components mean
the entire difference cannot be presented as verified parent-child overlap
within the retrieved cohort.
- Largest returned award record in the documented FY2020–FY2025 lookup:
  $448,283,318, OT2HL161847, FY2021. This is a scoped historical query result,
  not an all-time maximum or a verified lifetime project value.

Sources: docs/demonstration_fixture_double_counting/raw_records.json,
raw_records.sha256, decision_ledger.csv and independent_total.md;
docs/demonstration_fixture/RUN_MANIFEST.md, A5 LF-2, LF-3, LF-4, LF-7, LF-10.
-->

---

<!-- Slide 6: Boundaries and observed abstention -->

## Useful answers include a clear stopping point

| Question | Supported boundary |
|---|---|
| “Which R01 has run longest?” | No supported duration ranking. Decline the ranking. |
| “What happened to NIH-funded trainees?” | No workforce or longitudinal career-outcome integration. Explain the missing source. |
| “What is NIH's share of federal cancer spending?” | Provide a scoped NIH result if appropriate. Decline the government-wide comparison. |

USAspending comparison remains an **unregistered stub, outside the 14 active tools**.

Documented examples show abstention. Reliable behavior on every formulation remains unproven.

<!-- Speaker notes
Suggested boundary language, not a verbatim historical model quotation:
“These tools cannot rank grants by duration. I can retrieve project details,
but I cannot establish the longest-running R01 from this interface.”

“These tools do not provide individual trainee career trajectories. Training
award counts cannot answer a question about trainee outcomes.”

“I can report a defined NIH cohort. I cannot calculate the total federal share
because this submission has no implemented cross-agency spending integration.”

Evidence scope: EVAL_VERDICTS BC-3 records a zero-call abstention after the
v0.14.0 description changes, using Claude Sonnet 4-5. BC-3b records trainee-
outcomes abstention at v0.13.0 using GPT-5-5. BC-3c records a partial answer plus
decline of cross-agency comparison at v0.13.0. These are documented historical
cases, not a general abstention accuracy rate. The older 7/7 in-scope + 3/3
abstention battery was explicitly demoted and should not become a new headline.

Sources: docs/demonstration_fixture/EVAL_VERDICTS.md, BC-3, BC-3b, BC-3c and
STEP 4; docs/roadmap.md, “Stubbed, not implemented.”
-->

---

<!-- Slide 7: Evaluation evidence, mission alignment, and handoff -->

## Evidence a reviewer can inspect

| Evidence | What it supports |
|---|---|
| Release CI: **155 passed + 2 xfailed** | Selected model-free checks with explicit expected failures |
| Two frozen fixtures | Funding arithmetic, record decisions, and a parent-component double-counting example |
| Documented first-tool evaluation: **22/24** | Eight questions across three models, covering the original question set |

**Public review path:** tagged repository, fixtures, and run manifest. The Databricks app requires workspace access. Ask also requires model-endpoint authorization.

Inspectable portfolio analysis supports oversight. Clear scope and explanations support public access.

<!-- Speaker notes
The canonical release CI baseline is 155 passed + 2 xfailed. This deck rewrite
does not claim a new CI run. Keep the GitHub Actions run on the tagged commit
available for inspection. docs/evaluation.md section 3.1 lists the six CI
selections, including tests/test_version_contract.py, and sums to 155 + 2.

Model evaluation: 22/24=91.67%, rounded to 92%, measures the first selected tool
in the eight-question legacy slice. It does not measure end-to-end answer
correctness, successful runtime execution, or the full 14-tool surface. The
documented rerun misses Q5 for GPT and Claude. EVAL_VERDICTS' displayed matrix
therefore contains seven unanimous cases, while evaluation.md/findings.md say
six. Resolve against raw traces before publishing a unanimity metric; this
deck omits it. Keep the original version/date attached to each model run.

Do not call the three-question, five-repeat observation proof of general
determinism. Do not promote the reported argument-validity rate to evidence
that every runtime precondition or final answer was correct. Those metrics are
unnecessary for this main presentation.

Optional secondary evidence, with actual run dates preserved: standalone
smoke 17/17; live correctness 8/8; live robustness 38 cases, of which six needed
retry. Mocked robustness Part C is already included in the CI total. These
different suites and reruns must not be added into an undifferentiated pass
count. The repository contains no raw live execution logs, so these descriptions
alone do not independently re-execute those claims.

Use retained historical notebook outputs only with their stated run identity.
The separately revised notebook is an unexecuted instrument until a fresh run
produces outputs. Do not present its revised cells as new measured evidence.
The app's present Ask status has not been established by this document review.
If unavailable at presentation time, display a prominent status message and
use the public frozen artifacts. Do not promise that an upstream-dependent
Evidence Bundle request “always works.”

Repository: https://github.com/conroyriodss/nih-reporter-mcp/tree/v0.14.6
Manifest: https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.6/docs/demonstration_fixture/RUN_MANIFEST.md
Fixtures: https://github.com/conroyriodss/nih-reporter-mcp/tree/v0.14.6/docs/demonstration_fixture

Sources: docs/evaluation.md, sections 1 and 3.5;
docs/demonstration_fixture/RUN_MANIFEST.md;
docs/demonstration_fixture/EVAL_VERDICTS.md, claims 1–7.
-->
