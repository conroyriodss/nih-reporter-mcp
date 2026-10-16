# Independent Whole-Award Total: Double-Counting Proof

**Grant family:** U19AG068753 (Precision Monitoring and Assessment in the Framingham Study)
**FY:** 2024
**Retrieval date:** 2026-10-16T17:09:00.163212+00:00
**Purpose:** Demonstrate that excluding subprojects prevents real double-counting.

## The Double-Counting Problem

Per the NIH RePORTER Data Elements PDF: "For multi-project grants, Total_Cost
includes funding for all the constituent subprojects." This means the parent
award's `award_amount` already includes its children. Summing both double-counts.

## Raw Data (8 records)

| appl_id | role | subproject_id | award_amount |
|---:|---|---:|---:|
| 10903930 | PARENT | — | $   5,130,473 |
| 10903931 | sub 8052 | 8052 | $     574,217 |
| 10903932 | sub 5588 | 5588 | $   2,277,855 |
| 10903934 | sub 8054 | 8054 | $     486,044 |
| 10903936 | sub 8056 | 8056 | $     549,775 |
| 10903938 | sub 8059 | 8059 | $     370,535 |
| 10903941 | sub 8063 | 8063 | $     498,933 |
| 10903942 | sub 8065 | 8065 | $     373,114 |

## Naive Sum (all_records)

Parent: $5,130,473 + Subprojects: $5,130,473 = **$10,260,946**

## Correct Total (whole_award)

Excluding 7 subprojects: **$5,130,473**

## The Proof

The delta is $5,130,473 — **exactly** equal to the sum of the 7 subproject
amounts. This proves the parent's award_amount already includes its children.
Naive summing double-counts 100% of the subproject amounts.

| Metric | Value |
|---|---:|
| Naive (all_records) total | $10,260,946 |
| Correct (whole_award) total | $5,130,473 |
| Delta (double-counted) | $5,130,473 |
| Overstatement | 100.0% |
| Subprojects excluded | 7 |
| Orphan children | 0 (parent is present in cohort) |
