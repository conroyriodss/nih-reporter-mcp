"""Unit tests for funding aggregation correctness.

Pure synthetic fixtures — no network calls.  Tests the aggregate_funding()
helper in utils.py against known oracle values from the NIH RePORTER
Data Elements PDF and adversarial audit cases.

Reference: "For multi-project grants, Total_Cost includes funding for
all the constituent subprojects."  Parent award totals already include
their subprojects' funding; summing both levels double-counts.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nih_reporter_mcp.utils import aggregate_funding

import pytest


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────

def _rec(appl_id, award_amount, subproject_id=None, core_project_num="P01XX000001",
         fiscal_year=2023):
    """Build a minimal synthetic RePORTER record."""
    return {
        "appl_id": appl_id,
        "award_amount": award_amount,
        "subproject_id": subproject_id,
        "core_project_num": core_project_num,
        "fiscal_year": fiscal_year,
    }


# Case 1: Multi-project grant.  Parent $1M already includes subprojects.
# Children are $300K and $200K.  Naive sum = $1.5M; correct = $1M.
MULTI_PROJECT = [
    _rec(1001, 1_000_000, subproject_id=None),     # parent
    _rec(1002, 300_000,   subproject_id="0001"),    # child
    _rec(1003, 200_000,   subproject_id="0002"),    # child
]

# Case 2: Same core project across 2 years + a supplement + one duplicate.
# FY2023 parent $500K + FY2024 parent $400K + supplement $50K (appl_id=2003)
# + duplicate of 2001 repeated at page boundary.
# Oracle (whole_award): $500K + $400K + $50K = $950K  (4 records, 1 deduped)
MULTI_YEAR_DEDUP = [
    _rec(2001, 500_000, fiscal_year=2023),
    _rec(2002, 400_000, fiscal_year=2024),
    _rec(2003, 50_000,  fiscal_year=2023),   # supplement, no subproject_id
    _rec(2001, 500_000, fiscal_year=2023),   # exact duplicate (page boundary)
]

# Case 3: Two overlapping topics ("cancer" + "breast cancer") with shared
# records.  appl_ids 3001 and 3002 appear in both.  3003 is unique to set B.
# Oracle: $1M (dedup overlaps), NOT $1.3M.
OVERLAP_TOPICS = [
    _rec(3001, 400_000),
    _rec(3002, 300_000),
    _rec(3001, 400_000),  # overlap dup
    _rec(3002, 300_000),  # overlap dup
    _rec(3003, 300_000),  # unique to second topic
]

# Case 4: Records with missing (None) award_amount.
MISSING_AMOUNTS = [
    _rec(4001, 500_000),
    _rec(4002, None),       # missing
    _rec(4003, 300_000),
    _rec(4004, None),       # missing
]


# ────────────────────────────────────────────────────────────────────────
# Tests: whole_award mode (the new correct default)
# ────────────────────────────────────────────────────────────────────────

def test_multiproject_whole_award():
    """Parent $1M + two children → whole_award = $1M, not $1.5M."""
    agg = aggregate_funding(MULTI_PROJECT, funding_basis="whole_award")
    assert agg.total_award == 1_000_000, f"Expected 1M, got {agg.total_award}"
    assert agg.subproject_excluded_count == 2
    assert agg.record_count == 1  # only the parent counted


def test_multiproject_all_records():
    """all_records mode preserves legacy behavior: $1.5M."""
    agg = aggregate_funding(MULTI_PROJECT, funding_basis="all_records")
    assert agg.total_award == 1_500_000
    assert agg.subproject_excluded_count == 0
    assert agg.record_count == 3


def test_multiyear_dedup():
    """Cross-year + supplement + duplicate → $950K, deduped_count=1."""
    agg = aggregate_funding(MULTI_YEAR_DEDUP, funding_basis="whole_award")
    assert agg.total_award == 950_000, f"Expected 950K, got {agg.total_award}"
    assert agg.deduped_count == 1
    assert agg.record_count == 3  # 2001, 2002, 2003 (2001 dup skipped)


def test_overlap_dedup():
    """Overlapping topics with shared appl_ids → $1M, not $1.3M."""
    agg = aggregate_funding(OVERLAP_TOPICS, funding_basis="whole_award")
    assert agg.total_award == 1_000_000, f"Expected 1M, got {agg.total_award}"
    assert agg.deduped_count == 2


def test_missing_amounts_not_zeroed():
    """None amounts tracked separately, not counted as $0."""
    agg = aggregate_funding(MISSING_AMOUNTS, funding_basis="whole_award")
    assert agg.total_award == 800_000
    assert agg.records_with_missing_amount == 2
    assert agg.record_count == 4  # all 4 eligible (2 with amount, 2 missing)
    assert agg.contributing_count == 2  # only 2 contributed dollars


# ────────────────────────────────────────────────────────────────────────
# Finding A: study_section + investigator whole_award treatment
# ────────────────────────────────────────────────────────────────────────


def test_study_section_whole_award():
    """Per-group summation via aggregate_funding excludes subprojects.
    Parent $1M + $300K + $200K children in one section → $1M."""
    records = [
        {"appl_id": 101, "subproject_id": None, "award_amount": 1_000_000,
         "fiscal_year": 2023},
        {"appl_id": 102, "subproject_id": "0001", "award_amount": 300_000,
         "fiscal_year": 2023},
        {"appl_id": 103, "subproject_id": "0002", "award_amount": 200_000,
         "fiscal_year": 2023},
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 1_000_000, f"Expected $1M, got ${agg.total_award}"
    assert agg.subproject_excluded_count == 2
    assert agg.record_count == 1


def test_investigator_whole_award():
    """Investigator sum via aggregate_funding excludes subprojects.
    Same $1M parent + children fixture."""
    records = [
        {"appl_id": 201, "subproject_id": None, "award_amount": 1_000_000,
         "fiscal_year": 2023},
        {"appl_id": 202, "subproject_id": "0001", "award_amount": 300_000,
         "fiscal_year": 2023},
        {"appl_id": 203, "subproject_id": "0002", "award_amount": 200_000,
         "fiscal_year": 2023},
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 1_000_000
    assert agg.subproject_excluded_count == 2


# ────────────────────────────────────────────────────────────────────────
# Finding B: contributing_ids are post-exclusion
# ────────────────────────────────────────────────────────────────────────


def test_contributing_ids_post_exclusion():
    """contributing_ids contains ONLY IDs that contributed dollars.
    contributing_count matches len(contributing_ids)."""
    records = [
        _rec(301, 1_000_000, subproject_id=None),   # contributes
        _rec(302, 300_000,   subproject_id="0001"),  # excluded (subproject)
        _rec(303, None,      subproject_id=None),    # excluded (missing amount)
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.contributing_ids == [301]
    assert agg.contributing_count == 1
    assert agg.contributing_count == len(agg.contributing_ids)
    assert agg.total_award == 1_000_000
    assert agg.records_with_missing_amount == 1
    assert agg.record_count == 2  # eligible: parent (301) + null-amount (303)


# ────────────────────────────────────────────────────────────────────────
# Finding C: page-boundary duplicate completeness
# ────────────────────────────────────────────────────────────────────────


def test_page_boundary_completeness():
    """Pages [A,B],[B] with total=3: distinct IDs (2) < total (3) → incomplete.
    Old logic (row count 3 >= 3) was fooled; new logic catches it."""
    all_results = [
        {"appl_id": 1, "award_amount": 100},   # page 1
        {"appl_id": 2, "award_amount": 200},   # page 1
        {"appl_id": 2, "award_amount": 200},   # page 2 (boundary dup)
    ]
    total = 3  # API says 3 unique records exist
    distinct = {r["appl_id"] for r in all_results}
    complete_old = len(all_results) >= total   # True (WRONG)
    complete_new = len(distinct) >= total      # False (CORRECT)
    assert complete_old is True, "Old logic should have been fooled"
    assert complete_new is False, "New logic must detect the missing record"


# ────────────────────────────────────────────────────────────────────────
# Finding D: conflicting-duplicate resolution
# ────────────────────────────────────────────────────────────────────────


def test_conflicting_duplicate_flagged():
    """Same appl_id with DIFFERENT amounts → counted once but flagged.
    Test both orderings: the total is deterministic (first-wins) and
    the conflict flag is always raised."""
    records_a = [
        _rec(401, 1_000_000),
        _rec(401, 1_500_000),  # same ID, different amount
    ]
    records_b = [
        _rec(401, 1_500_000),  # reversed order
        _rec(401, 1_000_000),
    ]
    agg_a = aggregate_funding(records_a, funding_basis="whole_award")
    agg_b = aggregate_funding(records_b, funding_basis="whole_award")
    # First-wins in each order
    assert agg_a.total_award == 1_000_000
    assert agg_b.total_award == 1_500_000
    # Both flag the conflict
    assert agg_a.deduped_count == 1
    assert agg_b.deduped_count == 1
    assert 401 in agg_a.id_conflicts
    assert 401 in agg_b.id_conflicts


def test_identical_duplicate_silent():
    """Same appl_id with IDENTICAL data → collapsed silently, no conflict."""
    records = [
        _rec(501, 1_000_000),
        _rec(501, 1_000_000),  # exact page-boundary duplicate
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 1_000_000
    assert agg.deduped_count == 1
    assert len(agg.id_conflicts) == 0


# ────────────────────────────────────────────────────────────────────────
# Finding E: missing amounts propagated
# ────────────────────────────────────────────────────────────────────────


def test_missing_amount_propagated():
    """aggregate_funding tracks missing amounts for propagation."""
    records = [
        _rec(601, 500_000),
        _rec(602, None),
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.records_with_missing_amount == 1
    assert agg.total_award == 500_000
    assert agg.contributing_ids == [601]  # 602 missing, not in contributing


# ────────────────────────────────────────────────────────────────────────
# Guards for features not yet built (xfail)
# ────────────────────────────────────────────────────────────────────────

@pytest.mark.xfail(reason="IC-level attribution not yet implemented")
def test_ic_attribution():
    """Guard: when we add IC-level breakdowns, a multi-IC parent must not
    be attributed entirely to each IC."""
    # Placeholder — document intended behavior before implementing.
    assert False, "IC attribution not yet built"


@pytest.mark.xfail(reason="Publication-to-funding-year join not supported")
def test_publication_year_join():
    """Guard: NIH's FAQ states publication associations cannot identify
    a funding year.  Ensure we never add a year-attribution join."""
    assert False, "Publication year attribution deliberately unsupported"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
