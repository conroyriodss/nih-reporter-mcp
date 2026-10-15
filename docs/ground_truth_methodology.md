# Ground-Truth Methodology: Whole-Award Funding Verification

This document defines the procedure for independently verifying that this server's
reported funding totals are correct. Both `tests/test_correctness.py` and
`docs/demonstration_fixture/` implement this procedure.

This is the **documented method**, not runtime code. The server's `aggregate_funding()`
function in `src/nih_reporter_mcp/utils.py` implements the same logic at runtime; this
document exists so the logic can be verified without reading the implementation.

## Background

NIH RePORTER returns one record per funded award component. For multi-project grants
(U19, P01, etc.), the parent award record's `award_amount` already includes the funding
for all constituent subprojects. Subproject records also carry their own `award_amount`.
Naively summing all records double-counts multi-project grants.

**Source:** NIH RePORTER Data Elements PDF: "For multi-project grants, Total_Cost
includes funding for all the constituent subprojects."

## Whole-Award Rules

Given a set of raw RePORTER project records for a query:

### Step 1: Paginate all matching records

POST the query criteria to `https://api.reporter.nih.gov/v2/projects/search` with
`offset` incremented in steps of 500 (the page size), up to the configured retrieval
cap of 10,000 records (20 pages × 500). Collect all returned records.

### Step 2: Exclude subproject records

Remove any record whose `subproject_id` field is non-null. These are constituent
parts of a multi-project grant; their funding is already included in the parent
award's `award_amount`. Count the excluded records as `subproject_excluded_count`.

### Step 3: Deduplicate by appl_id

Records may appear on multiple pages due to page-boundary overlaps or repeated
API results. For each `appl_id`, keep the first occurrence only.

If a duplicate has *different* `award_amount`, `fiscal_year`, or `subproject_id`
from the first occurrence, record the `appl_id` in `id_conflicts` (the first
occurrence's values are counted; the conflict is flagged for manual investigation).

If a duplicate is *identical* to the first occurrence, it collapses silently
(no conflict).

### Step 4: Exclude records with null award_amount

Remove any record whose `award_amount` is null. These are tracked separately as
`records_with_missing_amount` — they are NOT zeroed to $0, which would silently
understate the missing-data problem.

### Step 5: Sum award_amount

Sum the `award_amount` field over all remaining records. This is the
**whole_award total**. The records that contributed to this sum are the
**contributing records**; their `appl_id` values are the **contributing appl_ids**.

## Completeness

The total is **complete** if the number of distinct `appl_id` values seen across
all pages equals or exceeds the `meta.total` reported by the API. If the query
matches more records than the retrieval cap, the total is a lower bound (flagged
with `complete=False`).

## Verification Procedure

To independently verify a reported figure:

1. Re-execute the query (the exact `query_criteria` is in the provenance)
2. Apply steps 1–5 above independently of the server code
3. Compare the resulting total to the server's reported `total_award_amount_usd`
4. Compare the contributing appl_ids to the server's `source_record_ids`
5. All must match to the dollar

## Applicability

This procedure is used by:

* `tests/test_correctness.py` — automated verification against live data
* `docs/demonstration_fixture/` — frozen, manually-verified artifact
* `eval/smoke_tests.py` t14 — provenance and counting-unit transparency check
