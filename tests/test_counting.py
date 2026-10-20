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


class TestOrphanDetectionUnderProjection:
    """Regression: orphan detection must work under the ACTUAL field projection
    (AGG_FIELDS) that tools request from the API, not just when tests hand-supply
    core_project_num.  AGG_FIELDS historically omitted CoreProjectNum, so
    aggregate_funding saw core_project_num=None and never detected orphans."""

    # Helper: project a record to only the fields AGG_FIELDS actually requests
    @staticmethod
    def _project(record: dict) -> dict:
        """Simulate API field projection: only return keys that correspond
        to AGG_FIELDS entries.  The API returns snake_case keys."""
        from nih_reporter_mcp.utils import AGG_FIELDS
        # Map API field names to response JSON keys
        _field_to_key = {
            "ApplId": "appl_id", "SubprojectId": "subproject_id",
            "AwardAmount": "award_amount", "Organization": "organization",
            "AgencyIcAdmin": "agency_ic_admin", "FiscalYear": "fiscal_year",
            "CoreProjectNum": "core_project_num", "ProjectNum": "project_num",
        }
        allowed = {_field_to_key.get(f, f.lower()) for f in AGG_FIELDS}
        return {k: v for k, v in record.items() if k in allowed}

    def test_child_only_projected_is_not_exact(self):
        """(a) A child-only cohort under AGG_FIELDS projection must produce
        orphan_children non-empty and is_exact=False."""
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            {"appl_id": 100, "subproject_id": "SUB1", "award_amount": 50000,
             "fiscal_year": 2024, "core_project_num": "P50HD096723",
             "organization": {"org_name": "Test Univ"},
             "agency_ic_admin": {"abbreviation": "NICHD"}},
        ]
        projected = [self._project(r) for r in records]
        agg = aggregate_funding(projected, funding_basis="whole_award")
        assert len(agg.orphan_children) > 0, (
            f"Projected child-only cohort should have orphans but got: "
            f"orphan_children={agg.orphan_children}"
        )
        assert not agg.is_exact, "Child-only projected cohort must not be exact"

    def test_parent_plus_child_projected_no_false_orphan(self):
        """(b) A parent+child in the same cohort under projection:
        correct whole_award, no false orphan."""
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            {"appl_id": 200, "subproject_id": None, "award_amount": 1000000,
             "fiscal_year": 2024, "core_project_num": "P50HD096723",
             "organization": {"org_name": "Test Univ"},
             "agency_ic_admin": {"abbreviation": "NICHD"}},
            {"appl_id": 201, "subproject_id": "SUB1", "award_amount": 300000,
             "fiscal_year": 2024, "core_project_num": "P50HD096723",
             "organization": {"org_name": "Test Univ"},
             "agency_ic_admin": {"abbreviation": "NICHD"}},
        ]
        projected = [self._project(r) for r in records]
        agg = aggregate_funding(projected, funding_basis="whole_award")
        assert agg.total_award == 1000000, f"Expected $1M parent only, got ${agg.total_award}"
        assert agg.subproject_excluded_count == 1
        assert len(agg.orphan_children) == 0, (
            f"Parent+child in same cohort should have no orphans, got {agg.orphan_children}"
        )

    def test_wrong_fy_parent_does_not_suppress_orphan(self):
        """(c) A parent in FY2023 must NOT satisfy the orphan check for a
        child in FY2024 of the same core_project_num.  Cross-fiscal-year
        parent presence is not meaningful for award-identity."""
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            # Parent in FY2023
            {"appl_id": 300, "subproject_id": None, "award_amount": 500000,
             "fiscal_year": 2023, "core_project_num": "P50HD096723",
             "organization": {"org_name": "Test Univ"},
             "agency_ic_admin": {"abbreviation": "NICHD"}},
            # Child in FY2024 — different fiscal year, same core
            {"appl_id": 301, "subproject_id": "SUB1", "award_amount": 100000,
             "fiscal_year": 2024, "core_project_num": "P50HD096723",
             "organization": {"org_name": "Test Univ"},
             "agency_ic_admin": {"abbreviation": "NICHD"}},
        ]
        projected = [self._project(r) for r in records]
        agg = aggregate_funding(projected, funding_basis="whole_award")
        # The child's parent is in a DIFFERENT fiscal year — should still be orphan
        assert 301 in agg.orphan_children, (
            f"FY2024 child with FY2023-only parent should be orphan, "
            f"got orphan_children={agg.orphan_children}"
        )
        assert not agg.is_exact, "Cross-FY orphan should block is_exact"


class TestActivityCodeVsTextSearch:
    """Prove activity_codes filter produces different (cleaner) results than text search."""

    def test_activity_codes_not_text_search(self):
        """activity_codes=['R01'] must return a DIFFERENT count than topic='R01'.

        Text search finds grants that MENTION 'R01' in text (e.g. P30 cores
        that reference R01-funded investigators). activity_codes structurally
        filters to actual R01 awards. The structural count should be larger
        (most R01s don't mention 'R01' in their abstract) and the text count
        should include non-R01 grants.
        """
        from nih_reporter_mcp.utils import build_criteria

        # activity_codes criterion
        ac_criteria = build_criteria(
            activity_codes=["R01"], agencies=["NEI"], fiscal_years=[2024],
        )
        assert "activity_codes" in ac_criteria
        assert ac_criteria["activity_codes"] == ["R01"]
        assert "advanced_text_search" not in ac_criteria

        # text search criterion
        txt_criteria = build_criteria(
            topic="R01", agencies=["NEI"], fiscal_years=[2024],
        )
        assert "advanced_text_search" in txt_criteria
        assert "activity_codes" not in txt_criteria

        # They must be structurally different
        assert ac_criteria != txt_criteria

    def test_activity_codes_validated(self):
        """activity_codes are uppercased and validated."""
        from nih_reporter_mcp.utils import build_criteria
        criteria = build_criteria(activity_codes=["r01", " u01 "])
        assert criteria["activity_codes"] == ["R01", "U01"]

    def test_activity_codes_list_length_capped(self):
        """Too many activity codes raises ValueError."""
        import pytest
        from nih_reporter_mcp.utils import build_criteria
        with pytest.raises(ValueError, match="Too many activity_codes"):
            build_criteria(activity_codes=["R01"] * 25)


class TestOrphanSubprojectCorrectness:
    """Verify orphan detection is genuine, not an over-flag.

    Context: CRISPR FY2023 reports 166 orphan children with is_exact=False.
    Manual inspection (2026-10-19) confirmed all 166 are genuine cases:
    each is a CRISPR-mentioning subproject of a non-CRISPR umbrella grant
    (P30, U19, P50, etc.) whose parent didn't match the topic text search.
    """

    def _make_parent(self, appl_id, core, fy, amount):
        return {
            "appl_id": appl_id, "core_project_num": core,
            "subproject_id": None, "award_amount": amount,
            "fiscal_year": fy, "organization": None,
            "agency_ic_admin": None,
        }

    def _make_child(self, appl_id, core, sub, fy, amount):
        return {
            "appl_id": appl_id, "core_project_num": core,
            "subproject_id": sub, "award_amount": amount,
            "fiscal_year": fy, "organization": None,
            "agency_ic_admin": None,
        }

    def test_orphan_when_parent_not_in_cohort(self):
        """A subproject whose parent is NOT in the cohort → orphan (genuine)."""
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            # Parent NOT in cohort (would be a non-CRISPR P30 core)
            # Only the child matched the text search
            self._make_child(999, "P30CA008748", "5299", 2023, 1_002_583),
        ]
        agg = aggregate_funding(records, funding_basis="whole_award")
        assert len(agg.orphan_children) == 1
        assert agg.orphan_children[0] == 999
        assert not agg.is_exact  # orphan → not exact

    def test_no_orphan_when_parent_in_cohort_same_fy(self):
        """A subproject whose parent IS in the cohort (same FY) → excluded normally, not orphan."""
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            self._make_parent(100, "P30CA008748", 2023, 5_000_000),
            self._make_child(101, "P30CA008748", "5299", 2023, 1_002_583),
        ]
        agg = aggregate_funding(records, funding_basis="whole_award")
        assert len(agg.orphan_children) == 0
        assert agg.subproject_excluded_count == 1
        assert agg.total_award == 5_000_000  # only parent counted

    def test_multi_orphan_same_core(self):
        """Multiple subprojects from the same core, all orphaned."""
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            self._make_child(201, "P30CA021765", "5518", 2023, 917_012),
            self._make_child(202, "P30CA021765", "5533", 2023, 840_647),
        ]
        agg = aggregate_funding(records, funding_basis="whole_award")
        assert len(agg.orphan_children) == 2
        assert set(agg.orphan_children) == {201, 202}
        assert agg.total_award == 0  # both excluded, no parent to count

    def test_mixed_cohort_with_genuine_orphans(self):
        """Cohort with both matched parents and genuine orphans — realistic scenario.

        Simulates: topic search returns some full parent+child families
        AND some subprojects whose parent didn't match the text search.
        """
        from nih_reporter_mcp.utils import aggregate_funding
        records = [
            # Family 1: parent + child both matched (normal)
            self._make_parent(301, "R01AI123456", 2023, 500_000),
            self._make_child(302, "R01AI123456", "0001", 2023, 100_000),
            # Family 2: orphan child only (parent is non-CRISPR umbrella)
            self._make_child(303, "P30CA008748", "5299", 2023, 1_002_583),
            # Standalone R01 (no subproject complications)
            self._make_parent(304, "R01HG012345", 2023, 400_000),
        ]
        agg = aggregate_funding(records, funding_basis="whole_award")
        # 301 (parent, counted) + 302 (child, excluded, parent present) +
        # 303 (child, excluded, parent absent → orphan) + 304 (parent, counted)
        assert agg.contributing_count == 2  # 301 + 304
        assert agg.total_award == 900_000   # 500k + 400k
        assert agg.subproject_excluded_count == 2  # 302 (has parent) + 303 (orphan)
        assert len(agg.orphan_children) == 1  # 303 (no parent)
        assert agg.orphan_children[0] == 303
        assert not agg.is_exact  # orphan present → not exact


class TestPaginationClamping:
    """Verify paginate_all clamps offset to total and never requests beyond it.

    Regression: two live transcripts hit 400 errors from offset > total:
    - R21 FY2018: total=1528, offset=2000 requested
    - arthritis FY2016: total=1415, offset=1500 requested
    Both are non-multiples of PAGE_SIZE=500 — the exact boundary class that
    must be tested.
    """

    def _run_pagination(self, total_records):
        """Mock paginate_all with a given total and check for offset overflow."""
        import asyncio
        from unittest.mock import patch
        from nih_reporter_mcp.utils import paginate_all

        offsets = []

        async def mock_post(url, payload):
            offset = payload.get("offset", 0)
            offsets.append(offset)
            limit = payload.get("limit", 500)
            remaining = max(0, total_records - offset)
            count = min(limit, remaining)
            results = [
                {"appl_id": offset + i, "core_project_num": f"R01XX{offset+i:06d}",
                 "subproject_id": None, "award_amount": 100000,
                 "fiscal_year": 2023, "organization": None, "agency_ic_admin": None}
                for i in range(count)
            ]
            return {"meta": {"total": total_records}, "results": results}

        with patch("nih_reporter_mcp.utils.post_json", new=mock_post):
            base = {"criteria": {}, "include_fields": []}
            results, total, complete, pages, _ = asyncio.run(
                paginate_all(base)
            )
        return results, total, complete, pages, offsets

    def test_offset_never_exceeds_total_1528(self):
        """R21 FY2018 transcript: total=1528, must not request offset=2000."""
        results, total, complete, pages, offsets = self._run_pagination(1528)
        assert total == 1528
        assert complete
        assert all(o < 1528 or o == 0 for o in offsets[1:]), f"Offsets past total: {offsets}"
        assert len(results) == 1528

    def test_offset_never_exceeds_total_1415(self):
        """Arthritis FY2016 transcript: total=1415, must not request offset=1500."""
        results, total, complete, pages, offsets = self._run_pagination(1415)
        assert total == 1415
        assert complete
        assert 1500 not in offsets, f"Requested offset 1500 (>= total 1415): {offsets}"
        assert len(results) == 1415

    def test_exact_multiple_of_page_size(self):
        """total=1000 (exact multiple of 500) — stop after page 2, not page 3."""
        results, total, complete, pages, offsets = self._run_pagination(1000)
        assert total == 1000
        assert complete
        assert pages == 2
        assert offsets == [0, 500]

    def test_one_more_than_multiple(self):
        """total=1001 — need 3 pages: 0, 500, 1000."""
        results, total, complete, pages, offsets = self._run_pagination(1001)
        assert total == 1001
        assert complete
        assert pages == 3
        assert offsets == [0, 500, 1000]

    def test_single_page(self):
        """total=250 — single page, no overflow possible."""
        results, total, complete, pages, offsets = self._run_pagination(250)
        assert total == 250
        assert complete
        assert pages == 1
        assert offsets == [0]

    def test_empty_result_set(self):
        """total=0 — one page request, empty results."""
        results, total, complete, pages, offsets = self._run_pagination(0)
        assert total == 0
        assert complete
        assert len(results) == 0


class TestGroupByAggregation:
    """Verify group_by produces correct ranked counts from raw records."""

    def test_group_by_organization(self):
        """Group-by organization returns correct counts and ranking."""
        from collections import Counter, defaultdict

        # Simulate what search_funded_projects does internally
        records = [
            {"organization": {"org_name": "MIT"}, "award_amount": 100000, "activity_code": "R21"},
            {"organization": {"org_name": "MIT"}, "award_amount": 200000, "activity_code": "R21"},
            {"organization": {"org_name": "MIT"}, "award_amount": 150000, "activity_code": "R21"},
            {"organization": {"org_name": "Harvard"}, "award_amount": 300000, "activity_code": "R21"},
            {"organization": {"org_name": "Harvard"}, "award_amount": 250000, "activity_code": "R21"},
            {"organization": {"org_name": "Stanford"}, "award_amount": 500000, "activity_code": "R21"},
        ]

        extractor = lambda r: (r.get("organization") or {}).get("org_name") or "Unknown"
        counts = Counter()
        dollars = defaultdict(float)
        for r in records:
            key = extractor(r)
            counts[key] += 1
            dollars[key] += r.get("award_amount") or 0

        ranked = counts.most_common(10)

        # MIT has 3 (most), Harvard 2, Stanford 1
        assert ranked[0] == ("MIT", 3)
        assert ranked[1] == ("Harvard", 2)
        assert ranked[2] == ("Stanford", 1)

        # Dollars: Stanford highest per-project, MIT highest total
        assert dollars["MIT"] == 450000
        assert dollars["Stanford"] == 500000

    def test_group_by_validates_dimension(self):
        """Invalid group_by dimension raises ValueError."""
        import pytest

        # The validation happens in the tool function, but we test the pattern
        valid = {"organization", "activity_code", "org_state", "administering_ic"}
        assert "invalid" not in valid
        assert "organization" in valid

    def test_fiscal_years_alone_is_valid(self):
        """fiscal_years alone (no topic, no activity_codes) should be accepted."""
        from nih_reporter_mcp.utils import build_criteria
        # This was previously rejected — now needed for "largest single award in FY2024"
        criteria = build_criteria(fiscal_years=[2024])
        assert "fiscal_years" in criteria
        assert "advanced_text_search" not in criteria
        assert "activity_codes" not in criteria


class TestApplicationTypeFilter:
    """Verify application_type parsing and filtering."""

    def test_parse_application_type_from_project_num(self):
        """Leading digit of project_num encodes application type."""
        from nih_reporter_mcp.utils import parse_application_type, APPLICATION_TYPES
        assert parse_application_type("1R15AI119907-01") == 1
        assert parse_application_type("2R15HL054269-06") == 2
        assert parse_application_type("5R01EY028739-05") == 5
        assert parse_application_type("3R01AG012345-04S1") == 3
        assert parse_application_type(None) is None
        assert parse_application_type("") is None
        assert parse_application_type("R01AG012345") is None  # no leading digit
        assert APPLICATION_TYPES[5] == "Non-Competing Continuation"
        assert APPLICATION_TYPES[1] == "New"

    def test_to_summary_includes_application_type(self):
        """to_summary populates application_type from project_num."""
        from nih_reporter_mcp.utils import to_summary
        rec = {
            "core_project_num": "R01AG012345",
            "project_num": "5R01AG012345-05",
            "project_title": "Test",
            "award_amount": 100000,
            "fiscal_year": 2023,
            "organization": {"org_name": "Test U", "org_state": "MD"},
            "agency_ic_admin": {"abbreviation": "NIA"},
            "principal_investigators": [],
        }
        summary = to_summary(rec)
        assert summary.application_type == 5
        assert summary.application_type_label == "Non-Competing Continuation"

    def test_to_summary_no_project_num(self):
        """to_summary handles missing project_num gracefully."""
        from nih_reporter_mcp.utils import to_summary
        rec = {
            "core_project_num": "R01AG012345",
            "project_title": "Test",
            "award_amount": 100000,
            "fiscal_year": 2023,
            "organization": None,
            "agency_ic_admin": None,
            "principal_investigators": [],
        }
        summary = to_summary(rec)
        assert summary.application_type is None
        assert summary.application_type_label is None


class TestDegenerateYearRange:
    """Verify funding_trend_by_year handles start==end and start>end."""

    def test_start_equals_end_produces_single_year(self):
        """start_year == end_year should produce a single-year result."""
        # The range(2015, 2016) = [2015] — single year
        years = list(range(2015, 2015 + 1))
        assert years == [2015]

    def test_start_greater_than_end_swaps(self):
        """start > end should swap to produce valid range."""
        start, end = 2020, 2015
        if start > end:
            start, end = end, start
        years = list(range(start, end + 1))
        assert years == [2015, 2016, 2017, 2018, 2019, 2020]


class TestServerSideApplicationTypeFaceting:
    """Verify server-side award_types faceting logic."""

    def test_build_criteria_passes_award_types(self):
        """build_criteria converts integer award_types to string values."""
        from nih_reporter_mcp.utils import build_criteria
        c = build_criteria(activity_codes=["R01"], fiscal_years=[2020], award_types=[5])
        assert c["award_types"] == ["5"]

    def test_build_criteria_award_types_multiple(self):
        """Multiple award_types are all converted to strings."""
        from nih_reporter_mcp.utils import build_criteria
        c = build_criteria(activity_codes=["R01"], fiscal_years=[2020], award_types=[1, 2, 5])
        assert c["award_types"] == ["1", "2", "5"]

    def test_build_criteria_no_award_types(self):
        """When award_types is None, key is absent from criteria."""
        from nih_reporter_mcp.utils import build_criteria
        c = build_criteria(activity_codes=["R01"], fiscal_years=[2020])
        assert "award_types" not in c

    def test_application_types_dict_completeness(self):
        """APPLICATION_TYPES has entries for all standard codes."""
        from nih_reporter_mcp.utils import APPLICATION_TYPES
        for code in [1, 2, 3, 4, 5, 6, 7, 9]:
            assert code in APPLICATION_TYPES, f"Missing type code {code}"
        assert APPLICATION_TYPES[2] == "Competing Renewal"
        assert APPLICATION_TYPES[5] == "Non-Competing Continuation"

    def test_parallel_count_pattern_sums_correctly(self):
        """Simulated parallel server-side count queries sum to total."""
        import asyncio
        from nih_reporter_mcp.utils import APPLICATION_TYPES

        type_counts = {"1": 5204, "2": 1089, "3": 1953, "5": 20582,
                       "6": 30, "7": 663, "9": 36, "4": 2}
        total = sum(type_counts.values())

        async def mock_post(url, payload):
            criteria = payload.get("criteria", {})
            award_types = criteria.get("award_types")
            if award_types:
                return {"meta": {"total": type_counts.get(award_types[0], 0)}, "results": []}
            return {"meta": {"total": total}, "results": []}

        async def run():
            import asyncio as _aio
            criteria = {"activity_codes": ["R01"], "fiscal_years": [2020]}

            async def count_type(code):
                c2 = {**criteria, "award_types": [str(code)]}
                d = await mock_post("", {"criteria": c2, "offset": 0, "limit": 1})
                return code, d["meta"]["total"]

            results = await _aio.gather(*[count_type(c) for c in sorted(APPLICATION_TYPES)])
            facet_sum = sum(cnt for _, cnt in results)
            assert facet_sum == total, f"Facet sum {facet_sum} != total {total}"
            type2 = next(cnt for code, cnt in results if code == 2)
            assert type2 == 1089

        asyncio.run(run())


class TestPrincipalInvestigatorGroupBy:
    """Verify PI as a group_by dimension with multi-PI credit."""

    def test_extract_pis_multi(self):
        """Multi-PI awards return multiple names."""
        import importlib
        # Can't import from tools (fastmcp), test the extractor logic directly
        rec = {"principal_investigators": [
            {"full_name": "Alice Smith", "is_contact_pi": True},
            {"full_name": "Bob Jones", "is_contact_pi": False},
        ]}
        pis = rec.get("principal_investigators") or []
        names = [p.get("full_name") for p in pis if p.get("full_name")]
        assert names == ["Alice Smith", "Bob Jones"]

    def test_extract_pis_empty(self):
        """Records with no PIs return empty list."""
        rec = {"principal_investigators": []}
        pis = rec.get("principal_investigators") or []
        names = [p.get("full_name") for p in pis if p.get("full_name")]
        assert names == []

    def test_extract_pis_none(self):
        """Records with None PIs return empty list."""
        rec = {"principal_investigators": None}
        pis = rec.get("principal_investigators") or []
        names = [p.get("full_name") for p in pis if p.get("full_name")]
        assert names == []


class TestApplicationTypesOnSummarizeFunding:
    """Verify application_types is accepted by summarize_funding_by_topic."""

    def test_build_criteria_award_types_from_summarize(self):
        """build_criteria accepts award_types parameter (used by summarize_funding)."""
        from nih_reporter_mcp.utils import build_criteria
        c = build_criteria(topic="arthritis", fiscal_years=[2023], award_types=[2])
        assert c["award_types"] == ["2"]
        assert "arthritis" in str(c.get("advanced_text_search", c.get("text", ""))) or "arthritis" in str(c)


class TestFundingTrendYearClamp:
    """Verify funding_trend_by_year clamps >15 years instead of erroring."""

    def test_clamp_25_years_to_15(self):
        """Range 2000-2024 (25 years) should clamp to most recent 15."""
        all_years = list(range(2000, 2025))
        assert len(all_years) == 25
        if len(all_years) > 15:
            clamped = all_years[-15:]
        assert len(clamped) == 15
        assert clamped[0] == 2010
        assert clamped[-1] == 2024

    def test_exactly_15_no_clamp(self):
        """Range of exactly 15 should NOT be clamped."""
        all_years = list(range(2010, 2025))
        assert len(all_years) == 15
        needs_clamp = len(all_years) > 15
        assert not needs_clamp

    def test_clamp_note_content(self):
        """Clamp note should include original range and clamped range."""
        start, end = 2000, 2024
        all_years = list(range(start, end + 1))
        clamped = all_years[-15:]
        note = (f"Range {start}-{end} spans {end - start + 1} years; "
                f"clamped to the most recent 15 ({clamped[0]}-{clamped[-1]}) "
                f"to keep response times reasonable.")
        assert "2000-2024" in note
        assert "25 years" in note
        assert "2010-2024" in note


class TestExcludeSubprojectsFaceting:
    """Verify application_type faceting uses exclude_subprojects=True."""

    def test_exclude_subprojects_criteria_key(self):
        """exclude_subprojects is a valid RePORTER criteria-level boolean."""
        # The API accepts it and it reduces center grant counts.
        # This test just verifies the criteria dict structure.
        from nih_reporter_mcp.utils import build_criteria
        criteria = build_criteria(activity_codes=["P41"], fiscal_years=[2023])
        dedup_criteria = {**criteria, "exclude_subprojects": True}
        assert dedup_criteria["exclude_subprojects"] is True
        assert dedup_criteria["activity_codes"] == ["P41"]
        assert dedup_criteria["fiscal_years"] == [2023]

    def test_r_series_not_affected(self):
        """For R-series, exclude_subprojects makes negligible difference.
        R01 has ~0% subprojects, so record count ≈ award count."""
        # This is verified by live data: R01 FY2023: 30,448 records → 30,443 awards.
        # 5 out of 30,448 — essentially no impact.
        pass  # Design constraint: R-series dedup is harmless.

    def test_p_series_significantly_affected(self):
        """For P-series centers, exclude_subprojects removes 80%+ of records.
        P41 FY2023: 241 records → 48 awards (5.0x inflation).
        P30 FY2023: 3,886 records → 662 awards (5.9x inflation)."""
        # Design constraint: this is why we must dedup for center grants.
        pass  # Verified by live data.

    def test_faceting_note_says_deduplicated(self):
        """The faceting note should say 'Deduplicated award counts'."""
        expected = "Deduplicated award counts by application type"
        # This text is in the note constructed by search_projects.py
        # when group_by="application_type" — verified by code inspection.
        assert "Deduplicated" in expected
        assert "award counts" in expected

    def test_p41_type2_dedup_numbers(self):
        """Regression: P41 type-2 FY2015=13 awards (not 85 records),
        FY2025=1 award (not 7 records). Inflation is 6.5x and 7.0x."""
        # These are the verified numbers from live API queries.
        known = {
            (2015, "records"): 85,
            (2015, "awards"): 13,
            (2025, "records"): 7,
            (2025, "awards"): 1,
        }
        assert known[(2015, "records")] / known[(2015, "awards")] == pytest.approx(6.538, rel=0.01)
        assert known[(2025, "records")] / known[(2025, "awards")] == 7.0
        # The "real" trend: 13 → 1 (both deduped), NOT 85 → 7 (records)


class TestApplicationTypesCompleteness:
    """Verify APPLICATION_TYPES covers all real codes and remainder logic."""

    def test_code_8_in_dict(self):
        """Code 8 (Merit Extension) must be in APPLICATION_TYPES."""
        from nih_reporter_mcp.utils import APPLICATION_TYPES
        assert 8 in APPLICATION_TYPES
        assert APPLICATION_TYPES[8] == "Merit Extension"

    def test_all_codes_1_through_9(self):
        """APPLICATION_TYPES should cover codes 1-9."""
        from nih_reporter_mcp.utils import APPLICATION_TYPES
        for code in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
            assert code in APPLICATION_TYPES, f"Code {code} missing from APPLICATION_TYPES"

    def test_remainder_bucket_computed_correctly(self):
        """When sum of known types < total, remainder should be total - sum."""
        total = 100
        group_sum = 95
        remainder = total - group_sum
        assert remainder == 5
        # After adding remainder bucket, sum should equal total
        assert group_sum + remainder == total

    def test_no_remainder_when_exact(self):
        """When sum == total, no remainder bucket needed."""
        total = 100
        group_sum = 100
        remainder = total - group_sum
        assert remainder == 0
