# Demo Script (~90 seconds)

> Narrated walkthrough of the NIH RePORTER MCP server. Every figure cited
> below matches either the frozen demonstration fixture
> (`docs/demonstration_fixture/`) or verified live API values from the
> automated test suite. No figure is aspirational.

---

## 0:00–0:15 — Pose a funding question

> "How much has NIH spent on CRISPR gene editing research in FY 2023?"

Show the tool call: `summarize_funding_by_topic` with
`topic="CRISPR gene editing"`, `fiscal_years=[2023]`,
`funding_basis="whole_award"`.

The answer comes back: **$836,981,580** with `complete=True` — every
matching record was retrieved. Note the distinction between matching and
contributing: **1,739 matching records** were returned by the API, but after
excluding 226 subproject records and 7 with missing amounts, **1,506 records
actually contributed** to the dollar total.

Point out what the response *includes* beyond the number: provenance
metadata, the exact query criteria, `records_aggregated=1,506` (contributing
count), `subproject_excluded_count=226`, and 7 records with missing amounts
tracked separately (not zeroed to $0).

## 0:15–0:35 — Open the evidence bundle

Call `export_evidence_bundle` for the same query. Show the response:

- **source_record_ids**: up to 500 of the 1,506 contributing appl_ids
  (capped at `MAX_PROVENANCE_IDS=500` for payload size);
  `records_aggregated` gives the true full count of 1,506.
- **reproduction_note**: a 5-step numbered procedure: (1) POST and
  paginate, (2) exclude subprojects, (3) deduplicate by appl_id,
  (4) exclude null amounts, (5) sum.
- **decision_ledger** (from the frozen fixture, "CRISPR sickle cell"
  FY 2024): open `decision_ledger.csv` — 38 rows, one per raw API
  record. Column `decision` shows 37 included, 1 excluded
  (appl_id 10992993, subproject of P50HD096723). That excluded record is
  an **orphan**: its parent P50HD096723 is not in the CRISPR sickle cell
  cohort, so it cannot demonstrate double-counting. The note flags this:
  the total covers only matching parent/non-subproject records.
  Column `amount_counted` sums to exactly **$19,790,134** — matching the
  tool's reported total to the dollar.

> "Every record's inclusion decision is inspectable. The orphan subproject
> is excluded and flagged — not silently dropped."

- **double-counting proof** (separate fixture,
  `docs/demonstration_fixture_double_counting/`): U19AG068753 FY2024 —
  1 parent ($5,130,473) + 7 subprojects (summing to $5,130,473) =
  $10,260,946 naive. The whole_award correction removes **exactly** the
  subproject amounts, yielding the parent's $5,130,473. This is the
  artifact that proves double-counting prevention is real:
  `decision_ledger.csv` shows 7 excluded children, each with its parent
  present in the cohort.

## 0:35–0:55 — RCDC vs. free-text comparison

Ask the agent an explicitly comparative question:

> "Compare NIH's official 'Long COVID' spending category total to a
> free-text search for 'long covid' in FY 2023."

The agent calls `summarize_funding_by_topic` twice — once with
`spending_category="long covid"` (RCDC), once with `topic="long covid"`
(free-text) — and surfaces a genuine finding:

| Method | FY 2023 Total |
|---|---|
| RCDC spending category | $199,600,750 |
| Free-text keyword search | $891,742,057 |

A **4.5× divergence** — the official category captures a curated subset;
the free-text search sweeps in every project mentioning the phrase.
The agent explains this distinction because both numbers are returned
with its provenance record; neither is presented as "the" answer.

## 0:55–1:10 — Citizen-scientist framing

Switch to the `citizen_scientist` prompt. Same data, different
presentation: plain-language summary, no jargon, dollar figures in
context ("roughly $837 million — about 1.8% of NIH's
$47.5 billion FY 2023 appropriation"). The prompt is one of 9 audience-tailored prompts (3 audience
groups: program officer, citizen scientist, PI/PD).

Show `explain_health_topic` calling MedlinePlus to provide accessible
context for the research area — the server reaches three upstream APIs
(RePORTER, NCBI E-utilities, MedlinePlus) to serve different audiences.

## 1:10–1:30 — Eval results and frozen proof

Show the test results:

- **38 unit tests passing + 2 xfailed** (planned future capabilities)
- **17/17 smoke tests** against live data — pagination, retrieval cap
  flagging, input validation, injection handling, whole_award vs.
  all_records dedup, cache correctness
- **8/8 correctness tests** — including `test_provenance_reproducibility`,
  which re-fetches the source_record_ids, independently applies the
  whole_award rules, and confirms the total reproduces exactly

Point to `docs/demonstration_fixture/`: a frozen, SHA-256-hashed snapshot
where `raw_records.json`, `decision_ledger.csv`, `independent_total.md`,
and `tool_output.json` all agree to the dollar. This is the artifact that
proves the differentiator — inspectable funding claims — is real, not
aspirational.

---

**Figures cited in this script and their sources:**

| Figure | Source | Verified |
|---|---|---|
| $836,981,580 (CRISPR FY2023 whole_award) | docs/findings.md Finding 11, smoke t1/t7 | Live API + tests |
| 1,739 matching records (1,506 contributing) | smoke t1, t7 | Live API |
| 10.1% all_records vs whole_award basis difference (not all duplication: 166 orphan subprojects) | docs/findings.md Finding 11 | Computed from verified figures |
| $19,790,134 (fixture cohort) | docs/demonstration_fixture/tool_output.json | Frozen + 3-way match |
| 38 records, 37 included, 1 excluded | docs/demonstration_fixture/decision_ledger.csv | Frozen |
| $199,600,750 (RCDC Long COVID) | smoke t4 | Live API |
| $891,742,057 (free-text long covid) | smoke t4 | Live API |
| 167 passed + 2 xfailed | CI selection in .github/workflows/ci.yml | Release CI |
| 17/17 smoke tests | eval/smoke_tests.py | Latest run |
| 8/8 correctness tests | tests/test_correctness.py | Live run (repository-reported) |
