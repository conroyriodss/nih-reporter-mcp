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


def test_page_boundary_dedup_logic():
    """Unit test for the completeness-detection logic itself (local
    set-cardinality check, does NOT exercise the paginator).

    Pages [A,B],[B] with total=3: distinct IDs (2) < total (3) → incomplete.
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
# Finding F: conflicting-duplicate must NEVER yield "exact"
# ────────────────────────────────────────────────────────────────────────


def test_conflicting_duplicate_blocks_exact_order_a():
    """Conflicting appl_id ($100K then $200K) must NOT yield is_exact=True.
    The conflict must surface regardless of provenance flag."""
    records = [
        _rec(701, 100_000),
        _rec(701, 200_000),  # same ID, different amount
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 100_000  # first-wins
    assert not agg.is_exact, "Conflicting duplicate must block is_exact"
    assert agg.has_unresolved_conflicts
    assert 701 in agg.id_conflicts


def test_conflicting_duplicate_blocks_exact_order_b():
    """Reversed ordering ($200K then $100K) must also block is_exact."""
    records = [
        _rec(701, 200_000),
        _rec(701, 100_000),  # reversed
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 200_000  # first-wins
    assert not agg.is_exact, "Conflicting duplicate must block is_exact (reversed)"
    assert agg.has_unresolved_conflicts
    assert 701 in agg.id_conflicts


def test_conflicting_duplicate_blocks_exact_all_records():
    """Conflict blocks is_exact in all_records mode too."""
    records = [
        _rec(701, 100_000),
        _rec(701, 200_000),
    ]
    agg = aggregate_funding(records, funding_basis="all_records")
    assert not agg.is_exact, "Conflicting duplicate must block is_exact (all_records)"
    assert 701 in agg.id_conflicts


def test_conflict_note_surfaces_without_provenance():
    """Even without provenance, the conflict count is available in AggResult.
    Tools must use agg.has_unresolved_conflicts to generate the note."""
    records = [
        _rec(801, 300_000),
        _rec(801, 400_000),
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    # These are the fields a tool must check to generate its note:
    assert agg.has_unresolved_conflicts
    assert len(agg.id_conflicts) == 1
    assert agg.records_with_missing_amount == 0
    # The tool should NOT say "exact" because of the conflict:
    assert not agg.is_exact


def test_clean_records_yield_exact():
    """Positive control: no conflicts, no missing, no orphans → is_exact=True."""
    records = [
        _rec(901, 500_000),
        _rec(902, 300_000),
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.is_exact
    assert not agg.has_unresolved_conflicts
    assert agg.records_with_missing_amount == 0
    assert len(agg.orphan_children) == 0


# ────────────────────────────────────────────────────────────────────────
# Finding G: orphan children must block is_exact
# ────────────────────────────────────────────────────────────────────────


def test_orphan_only_cohort_not_exact():
    """A cohort consisting only of orphan subprojects (whose parent is absent)
    must yield $0 total, contributing_count=0, and is_exact=False."""
    records = [
        _rec(10992993, 472999, subproject_id=9946, core_project_num="P50HD096723"),
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 0
    assert agg.contributing_count == 0
    assert agg.subproject_excluded_count == 1
    assert len(agg.orphan_children) == 1
    assert 10992993 in agg.orphan_children
    assert not agg.is_exact, "Orphan-only cohort must not be labeled exact"


def test_orphan_alongside_parents_blocks_exact():
    """Even when valid parent records contribute, orphan children still block
    is_exact because the total may not reflect full topical investment."""
    records = [
        _rec(901, 500_000),  # valid parent, contributes
        _rec(10992993, 472999, subproject_id=9946, core_project_num="P50HD096723"),
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 500_000  # only the parent counts
    assert agg.contributing_count == 1
    assert len(agg.orphan_children) == 1
    assert not agg.is_exact, "Orphan children present must block is_exact"


def test_non_orphan_subproject_does_not_block_exact():
    """A subproject whose parent IS in the cohort is not an orphan.
    Excluding it is correct double-counting prevention, not a warning."""
    records = [
        _rec(1001, 5_000_000, core_project_num="U19AG068753"),  # parent
        _rec(1002, 2_000_000, subproject_id=1, core_project_num="U19AG068753"),  # child of parent
        _rec(1003, 3_000_000, subproject_id=2, core_project_num="U19AG068753"),  # child of parent
    ]
    agg = aggregate_funding(records, funding_basis="whole_award")
    assert agg.total_award == 5_000_000  # parent only
    assert agg.subproject_excluded_count == 2
    assert len(agg.orphan_children) == 0  # not orphans — parent is present
    assert agg.is_exact  # no orphans, no conflicts, no missing


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


class TestReproductionNoteOrder:
    """GAP 2: The reproduction_note must describe the ACTUAL code order:
    deduplicate by appl_id FIRST, then exclude subprojects, then exclude
    null amounts, then sum. If the note says a different order, it's wrong."""

    def test_note_order_matches_code_dedup_before_subproject(self):
        """The reproduction_note for whole_award must say 'Deduplicate' before
        'Exclude subproject' — matching the actual aggregate_funding code."""
        from pathlib import Path
        eb_path = Path(__file__).parent.parent / "src" / "nih_reporter_mcp" / "tools" / "evidence_bundle.py"
        source = eb_path.read_text()
        # Find the whole_award reproduction note block — it starts after
        # 'if funding_basis == "whole_award":' and spans multiple string lines.
        marker = 'if funding_basis == "whole_award":'
        idx = source.find(marker)
        assert idx != -1, "Could not find whole_award branch in evidence_bundle.py"
        # Grab the next ~1000 chars which contain the full repro note
        note_block = source[idx:idx + 1500]

        # The note must describe dedup BEFORE subproject exclusion
        dedup_pos = note_block.find("eduplicate")  # "Deduplicate" or "deduplicate"
        subproject_pos = note_block.find("subproject_id")
        assert dedup_pos != -1, f"Reproduction note missing deduplicate step in: {note_block[:200]}"
        assert subproject_pos != -1, "Reproduction note missing subproject step"
        assert dedup_pos < subproject_pos, (
            f"Reproduction note says subproject exclusion (pos {subproject_pos}) "
            f"BEFORE deduplication (pos {dedup_pos}), but production code "
            f"deduplicates first. Note must match code order."
        )

    def test_aggregate_funding_dedup_then_exclude_on_conflict(self):
        """Synthetic proof: child-first, parent-second with same appl_id.
        Code deduplicates first (child wins), then excludes (child is subproject).
        If the order were reversed (exclude first, then dedup), the parent would
        survive and produce a different total."""
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            # Child seen first (subproject, $100)
            {"appl_id": 999, "subproject_id": "SUB1", "award_amount": 100,
             "fiscal_year": 2024, "core_project_num": "R01XX000001"},
            # Parent seen second (same appl_id, $500) — should be deduped
            {"appl_id": 999, "subproject_id": None, "award_amount": 500,
             "fiscal_year": 2024, "core_project_num": "R01XX000001"},
        ]
        agg = aggregate_funding(records, funding_basis="whole_award")
        # Production order: dedup first → child wins → then exclude subproject
        # → child excluded → total $0, with conflict flagged
        assert agg.total_award == 0, (
            f"Expected $0 (child wins dedup, then excluded as subproject), "
            f"got ${agg.total_award}"
        )
        assert agg.deduped_count == 1, "Parent should be deduped"
        assert agg.has_unresolved_conflicts, "Different amounts = conflict"
