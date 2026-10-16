# Demonstration Fixture: Double-Counting Proof

This fixture proves that parent/subproject double-counting is real and that the
whole_award correction removes exactly the right dollars.

## Grant Family

**U19AG068753** — *Precision Monitoring and Assessment in the Framingham Study*
(Boston University Medical Campus, NIA, FY 2024)

1 parent award + 7 subprojects = 8 records total.

## The Proof

The parent's `award_amount` ($5,130,473) already includes all 7 subprojects'
amounts (which also sum to $5,130,473). Naively summing all 8 records produces
$10,260,946 — **exactly double** the correct figure.

| Metric | Value |
|---|---:|
| Parent award | $5,130,473 |
| Sum of 7 subprojects | $5,130,473 |
| Naive total (all_records) | $10,260,946 |
| Correct total (whole_award) | $5,130,473 |
| Overstatement | 100.0% |

## Why This Family, Not the Frozen Fixture

The primary frozen fixture ("CRISPR sickle cell" FY2024, 38 records) demonstrates
correct aggregation and orphan detection, but its single excluded subproject
(appl_id 10992993 / P50HD096723) is an **orphan** — its parent is NOT in the
CRISPR sickle cell cohort. That exclusion is correct but does not prove
double-counting, because there is no parent to double-count against.

This U19AG068753 fixture has the complete family — parent and all children — so
the delta between all_records and whole_award is exactly the sum of subproject
amounts. That is the inspectable, reproducible proof that the correction removes
real double-counted dollars.

## Files

| File | Purpose |
|---|---|
| `query.json` | Exact criteria sent to the RePORTER API |
| `raw_records.json` | Complete raw API response, frozen with retrieval timestamp |
| `raw_records.sha256` | SHA-256 hash of the frozen data (tamper-evidence) |
| `decision_ledger.csv` | One row per record: appl_id, inclusion decision, reason, amount counted |
| `independent_total.md` | Hand-computed proof showing parent = sum(subprojects) = delta |

## Three-Way Match

* `decision_ledger.csv` sum(amount_counted): **$5,130,473**
* `independent_total.md` whole_award total: **$5,130,473**
* `independent_total.md` delta (naive − correct): **$5,130,473** (= sum of excluded subs)
