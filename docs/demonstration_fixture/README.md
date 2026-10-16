# Demonstration Fixture: Frozen, Independently-Verified Funding Claim

This is a frozen, independently-verified demonstration that our reported funding
figure is correct and reproducible. Every record's inclusion decision is in
`decision_ledger.csv`; the hand calculation in `independent_total.md` matches
the tool's output in `tool_output.json` to the dollar.

## Cohort

**"CRISPR sickle cell" FY2024** — chosen because it is small enough (38 records,
37 contributing) that `source_record_ids` is complete (not capped at 500), making
end-to-end verification possible without sampling.

**Note:** This fixture demonstrates correct aggregation, deduplication, and
orphan detection — but NOT double-counting. Its single excluded subproject
(appl_id 10992993, P50HD096723) is an **orphan**: its parent award is absent
from the CRISPR sickle cell cohort, so there is no parent to double-count
against. For the double-counting proof (parent + children in the same cohort),
see `docs/demonstration_fixture_double_counting/` (U19AG068753 FY2024).

## Files

| File | Purpose |
|---|---|
| `query.json` | Exact criteria sent to the RePORTER API |
| `raw_records.json` | Complete raw API response, frozen with retrieval timestamp |
| `raw_records.sha256` | SHA-256 hash of the frozen data (tamper-evidence) |
| `decision_ledger.csv` | One row per record: appl_id, inclusion decision, reason, amount counted |
| `independent_total.md` | Hand-computed whole_award total with full arithmetic |
| `tool_output.json` | What `export_evidence_bundle` returns for the same query |

## How to Verify

1. **Tamper check**: `sha256sum raw_records.json` must match `raw_records.sha256`.

2. **Ledger audit**: Open `decision_ledger.csv`. Every record from `raw_records.json`
   has a row. The `decision` column is `included` or `excluded`; the `reason` column
   explains why. Sum the `amount_counted` column.

3. **Independent total**: `independent_total.md` shows the arithmetic row by row.
   The total matches the ledger sum.

4. **Tool comparison**: `tool_output.json` is the live tool's output. Its
   `summary.total_award_amount_usd` must equal the ledger sum and independent total.

5. **Reproduction**: Follow the `reproduction_note` in `tool_output.json` literally
   (POST the query_criteria, paginate, exclude subprojects, dedup, drop nulls, sum).
   The result must match all three figures.

## Methodology

The whole_award rules applied here are documented in `docs/ground_truth_methodology.md`.
Both this fixture and `tests/test_correctness.py` implement that procedure.

## Three-Way Match

All three figures agree to the dollar:

* `decision_ledger.csv` sum(amount_counted): **$19,790,134.00**
* `independent_total.md` hand-computed total: **$19,790,134.00**
* `tool_output.json` total_award_amount_usd: **$19,790,134.00**
