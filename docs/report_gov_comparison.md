# RePORT.gov Ground-Truth Comparison

Verified 2026-10-19 against live RePORTER v2 API and published
report.nih.gov figures.  This document maps which RePORT.gov question
types this server answers accurately, which with documented caveats,
and which it must decline.

## Summary

| Capability | Status | Notes |
|---|:---:|---|
| Awards by state | **Match** | org_state filter → exact match with raw API |
| Awards by organization | **Match** | org_names / org_names_exact → exact match |
| Awards by city | **Gap** | API supports `org_cities` but our tools don't expose it |
| Awards by congressional district | **Gap** | API supports `cong_dists` but our tools don't expose it |
| RCDC categorical spending | **Caveat** | Live aggregation ≠ frozen published RCDC totals (Finding #3) |
| Activity-code filtering (R01, T32, etc.) | **Match** | Structural `activity_codes` filter → exact match |
| Training grant counts (T32, F32, K-series) | **Match** | Via `activity_codes` filter |
| Trainee outcomes / demographics | **Decline** | No data source in RePORTER |
| Workforce demographics | **Decline** | No data source in RePORTER |

---

## Category 1 — Awards by Location

### State-level filtering: MATCH

| Metric | Our tool | Independent curl | Match? |
|---|---|---|:---:|
| MA FY2023 total projects | 7,102 | 7,102 | YES |
| MA FY2023 whole_award total | $3,560,090,944 | (same criteria) | YES |
| MA FY2023 aggregated (post-dedup) | 6,060 | — | — |
| MA FY2023 complete | True | — | — |

Our `org_state` parameter maps directly to RePORTER's `org_states` criterion.
The count matches exactly. The dollar total is a live whole_award aggregation
(subprojects excluded, deduped).

### City-level filtering: GAP

The RePORTER API supports `org_cities` (tested: `org_cities=["Boston"]` →
5,174 results for FY2023). Our tools do not expose this filter.

**Decision:** Document as a gap. Adding `org_cities` to `build_criteria` is
low-effort (identical pattern to `org_state`) but not implemented in this
release.

### Congressional-district filtering: GAP

The RePORTER API supports `cong_dists` (tested: `cong_dists=["MA-07"]` →
4,303 results for FY2023). Our tools do not expose this filter.

**Decision:** Document as a gap. Same pattern as org_cities.

---

## Category 2 — Categorical (RCDC) Spending: CAVEAT

Our server aggregates live RePORTER data tagged with an RCDC spending
category. NIH's published figures on report.nih.gov/funding/categorical-spending
are **frozen point-in-time snapshots** produced by NIH's internal process.
These differ from live aggregation for several documented reasons (Finding #3):

- NIH's RCDC algorithm runs periodically and tags may change between snapshots
- RePORTER's live data includes corrections, late-loaded records, and retractions
  that post-date the published snapshot
- The 10,000-record retrieval ceiling clips large categories (Cancer hit this)

| RCDC Category | FY | Published (report.nih.gov) | Our live aggregation | Gap | Cause |
|---|---|---|---|---|---|
| Alzheimer's Disease | 2023 | ~$3.7B | $2,678,302,832 | −$1.0B (−28%) | Likely: ADRD subcategory differences, tagging lag |
| Cancer | 2023 | ~$7.8B | $6,597,567,243 | −$1.2B (−15%) | 10K-record ceiling clipped (15,453 total, only 10K fetched) |
| Sickle Cell Disease | 2023 | ~$161M | $168,917,919 | +$8M (+5%) | Small enough to complete; live data includes late corrections |

**This validates Finding #3.** Our documentation already states that live
aggregation may differ from published RCDC totals. The comparison confirms:

1. Small categories (Sickle Cell Disease) are close (±5%)
2. Medium categories (Alzheimer's) show meaningful divergence from tagging differences
3. Large categories (Cancer) are additionally clipped by the 10K ceiling

**We do NOT claim to replicate RCDC published figures.** Our tool says:
> "Aggregates live RePORTER data tagged with this category; note this may
> differ from NIH's frozen published RCDC totals, which are point-in-time
> snapshots."

---

## Category 3 — Activity-Code / Mechanism: MATCH

### R01 count at NEI FY2024

| Method | Count | $ Total |
|---|---|---|
| `activity_codes=["R01"]` (structural filter) | 1,079 | $482,952,475 |
| Independent raw curl (same criteria) | 1,079 | — |
| `topic="R01"` (text search — OLD path) | 204 | — |

The structural `activity_codes` filter matches the independent curl exactly.
The old text-search path missed **81% of actual R01 awards** (it only found
204 grants that mention "R01" in their text, including P30 cores that
reference R01 investigators).

### Why text search was wrong

Text search `topic="R01"` finds grants where "R01" appears in the title,
abstract, or terms. This is neither necessary (most R01s don't mention "R01"
in their abstract) nor sufficient (P30 center cores that say "supports
R01-funded investigators" match falsely).

### Training / career grants via activity_codes: MATCH

| Activity code | FY2024 count | Description |
|---|---|---|
| T32 | 1,760 | Training grants |
| F32 | 810 | Postdoctoral fellowships |
| K23 | 1,425 | Patient-oriented career development |

These are structural counts matching the API exactly. Any question of the
form "how many [activity-code] grants at [IC] in [FY]?" is now cleanly
answerable.

---

## Category 4 — Workforce / Training Questions

### Grant COUNTS by mechanism: MATCH (via activity_codes)

"How many T32 training grants in FY2024?" → 1,760 (exact, via
`activity_codes=["T32"]`).

### Trainee outcomes: DECLINE

RePORTER tracks **award records**, not trainee outcomes. Questions like:
- "What percentage of T32 trainees go on to R01 funding?"
- "What are the career outcomes for F32 postdocs?"
- "How long does it take K-award recipients to get R01s?"

require NIH's [Workforce Report](https://report.nih.gov/workforce) data,
which is a separate data product not available through the RePORTER API.

**Correct abstention:** "I can count training-grant awards by activity code
and fiscal year, but I don't have trainee-outcome or career-trajectory data.
That information is in NIH's Workforce Report, a separate data source."

### Workforce demographics: DECLINE

Questions about investigator demographics (age, gender, race, career stage)
require data from NIH's [Data Book](https://report.nih.gov/nihdatabook) and
the [Workforce Report](https://report.nih.gov/workforce), neither of which
is available through the RePORTER API.

---

## Location filter gaps — decision record

| Filter | API parameter | Supported by RePORTER? | Exposed by our tools? | Priority |
|---|---|:---:|:---:|---|
| State | `org_states` | YES | YES | — |
| City | `org_cities` | YES | **NO** | Low (add if requested) |
| Congressional district | `cong_dists` | YES | **NO** | Low (add if requested) |
| Country | `org_countries` | YES (likely) | **NO** | Low |
| ZIP code | — | Unknown | NO | — |

Adding any of these is a one-line change to `build_criteria` + parameter
on the relevant tools + input validation. Not implemented in this release
because no user question has required them.
