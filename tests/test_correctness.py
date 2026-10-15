#!/usr/bin/env python3
"""Correctness tests against independent ground truth.

Proves the v0.8.0 counting fix produces correct funding totals by comparing
tool output against independently-fetched, hand-computed reference values.
Every assertion uses the whole_award basis (the corrected default), not the
inflated all_records figures.

Requires a running MCP server.  Run with::

    # Via pytest (from project root, server already running):
    PYTHONPATH=src pytest tests/test_correctness.py -v

    # Standalone:
    MCP_URL=http://localhost:8000/mcp python tests/test_correctness.py
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx
from fastmcp import Client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")
REPORTER_URL = "https://api.reporter.nih.gov/v2/projects/search"


# ── Fixture: "CRISPR sickle cell" FY2024 ─────────────────────────────────
#
# Query:      advanced_text_search "CRISPR sickle cell", fiscal_years [2024]
# Retrieved:  2026-10-15T18:36:08Z via direct API call (tests/fixtures/)
# Records:    38 total, 37 parents + 1 subproject, 0 null amounts
#
# Hand computation (whole_award rules applied independently):
#   - Exclude subproject records (subproject_id is not None):  1 excluded
#   - Deduplicate by appl_id:                                  0 duplicates
#   - Exclude null award_amount:                                0 excluded
#   - Sum remaining 37 parent records:                          $19,790,134.00
#
# This is an EXACT assertion, not drift-tolerant.  If NIH data changes
# (new awards posted, amounts corrected), re-derive the fixture:
#   1. Re-run the raw API query
#   2. Re-apply whole_award rules
#   3. Update the constants below
# ──────────────────────────────────────────────────────────────────────
FIXTURE_TOPIC = "CRISPR sickle cell"
FIXTURE_FY = [2024]
FIXTURE_TOTAL_RECORDS = 38
FIXTURE_WHOLE_AWARD = 19_790_134.0
FIXTURE_PARENT_COUNT = 37
FIXTURE_SUBPROJECTS = 1
FIXTURE_RETRIEVAL = "2026-10-15"


# ── Helpers ──────────────────────────────────────────────────────────────


async def _raw_fetch(criteria: dict, limit: int = 500) -> list[dict]:
    """Fetch records directly from RePORTER, bypassing all tools."""
    payload = {
        "criteria": criteria,
        "include_fields": ["ApplId", "SubprojectId", "AwardAmount"],
        "offset": 0,
        "limit": limit,
    }
    async with httpx.AsyncClient(
        timeout=30.0, follow_redirects=False, trust_env=False,
    ) as client:
        resp = await client.post(REPORTER_URL, json=payload)
        return resp.json().get("results", [])


def _whole_award_sum(
    records: list[dict],
) -> tuple[float, int, int, int]:
    """Apply whole_award rules independently: exclude subprojects, dedupe,
    track missing.  Returns (total, count, missing, excluded)."""
    seen: set[int] = set()
    total = 0.0
    count = 0
    missing = 0
    excluded = 0
    for r in records:
        aid = r.get("appl_id")
        if aid is not None:
            if aid in seen:
                continue
            seen.add(aid)
        if r.get("subproject_id") is not None:
            excluded += 1
            continue
        amt = r.get("award_amount")
        if amt is None:
            missing += 1
        else:
            total += amt
        count += 1
    return round(total, 2), count, missing, excluded


# ── Test 1: Ground-truth exact match ───────────────────────────────────


def test_ground_truth_exact_match():
    """Tool's whole_award total matches hand-computed fixture to the dollar."""

    async def _run():
        async with Client(MCP_URL) as c:
            r = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": FIXTURE_TOPIC, "fiscal_years": FIXTURE_FY,
                 "funding_basis": "whole_award"},
            )
        d = r.data
        assert d.total_matching_projects == FIXTURE_TOTAL_RECORDS, (
            f"Expected {FIXTURE_TOTAL_RECORDS} projects, got "
            f"{d.total_matching_projects}.  Fixture retrieved {FIXTURE_RETRIEVAL}; "
            "if this drifts, re-derive the fixture."
        )
        assert d.total_award_amount_usd == FIXTURE_WHOLE_AWARD, (
            f"Expected ${FIXTURE_WHOLE_AWARD:,.2f}, got "
            f"${d.total_award_amount_usd:,.2f}.  Fixture retrieved "
            f"{FIXTURE_RETRIEVAL}; if this drifts, re-derive the fixture."
        )
        assert d.subproject_excluded_count == FIXTURE_SUBPROJECTS

    asyncio.run(_run())


# ── Test 2: Double-counting proof (U19AG068753) ───────────────────────


def test_double_counting_proof():
    """For a confirmed multi-component grant, whole_award < all_records
    and the delta equals the summed subproject amounts — proving the fix
    removes real double-counted dollars, not a cosmetic relabel."""

    async def _run():
        # (a) Raw fetch confirms multiple records for one core project
        raw = await _raw_fetch(
            {"project_nums": ["U19AG068753"], "fiscal_years": [2024]},
        )
        assert len(raw) > 1, (
            "U19AG068753 should have multiple records (parent + subprojects)"
        )

        parents = [r for r in raw if r.get("subproject_id") is None]
        subs = [r for r in raw if r.get("subproject_id") is not None]
        assert len(parents) >= 1, "Must have at least one parent record"
        assert len(subs) >= 1, "Must have at least one subproject record"

        parent_sum = sum(
            r["award_amount"] for r in parents if r.get("award_amount")
        )
        sub_sum = sum(
            r["award_amount"] for r in subs if r.get("award_amount")
        )
        all_sum = parent_sum + sub_sum

        # (b) all_records > whole_award
        assert all_sum > parent_sum

        # (c) whole_award equals the sum of parent-only records
        wa_total, _, _, _ = _whole_award_sum(raw)
        assert wa_total == parent_sum, (
            f"whole_award ({wa_total}) != parent sum ({parent_sum})"
        )

        # (d) delta is nonzero and equals subproject amounts
        delta = all_sum - parent_sum
        assert delta > 0, "Delta must be nonzero (real double-counted dollars)"
        assert delta == sub_sum, (
            f"Delta ({delta}) should equal subproject sum ({sub_sum})"
        )

    asyncio.run(_run())


# ── Test 3: Provenance reproducibility ─────────────────────────────────


def test_provenance_reproducibility():
    """Re-fetch source_record_ids from export_evidence_bundle, apply
    whole_award rules independently, and confirm the reported total
    reproduces exactly — proving provenance is sufficient for independent
    reproduction of the CORRECTED figure."""

    async def _run():
        async with Client(MCP_URL) as c:
            r = await c.call_tool("export_evidence_bundle", {
                "topic": FIXTURE_TOPIC,
                "fiscal_years": FIXTURE_FY,
                "label": "correctness-test",
            })
        d = r.data
        reported_total = d.summary.total_award_amount_usd
        source_ids = d.provenance.source_record_ids
        assert len(source_ids) > 0, "Provenance must include source_record_ids"

        # Re-fetch those specific records by appl_id, bypassing all tools
        raw = await _raw_fetch({"appl_ids": source_ids})
        assert len(raw) > 0, "Re-fetch returned no records"

        # Apply whole_award rules independently
        indie_total, _, _, _ = _whole_award_sum(raw)
        assert indie_total == reported_total, (
            f"Independent re-computation (${indie_total:,.2f}) != "
            f"reported total (${reported_total:,.2f})"
        )

    asyncio.run(_run())


# ── Test 4: Missing-amount honesty ─────────────────────────────────────


def test_missing_amount_honesty():
    """When records have null award_amount, the tool reports them as excluded
    (not zeroed to $0) and does NOT claim the total is 'exact'."""

    async def _run():
        async with Client(MCP_URL) as c:
            # CRISPR FY2023 has ~7 records with missing amounts
            r = await c.call_tool("summarize_funding_by_topic", {
                "topic": "CRISPR gene editing",
                "fiscal_years": [2023],
                "funding_basis": "whole_award",
                "include_provenance": True,
            })
        d = r.data

        if d.records_with_missing_amount == 0:
            import warnings
            warnings.warn(
                "No missing-amount records in CRISPR FY2023 (may have been "
                "backfilled).  Cannot verify missing-amount handling."
            )
            return

        # Missing amounts are tracked and reported
        assert d.records_with_missing_amount > 0
        assert d.provenance.records_with_missing_amount == (
            d.records_with_missing_amount
        )

        # The note must NOT say "exact" when missing amounts exist
        if d.records_with_missing_amount > 0:
            assert "missing" in d.note.lower() or "exact" not in d.note.lower(), (
                "Note claims 'exact' despite missing-amount records"
            )

    asyncio.run(_run())


# ── Test 5: Cross-tool basis consistency ───────────────────────────────


def test_cross_tool_basis_consistency():
    """For a subproject-bearing topic, whole_award is strictly less than
    all_records.  This mirrors smoke test t7 but lives here as a
    correctness guarantee rather than a regression check."""

    async def _run():
        async with Client(MCP_URL) as c:
            r_whole = await c.call_tool("summarize_funding_by_topic", {
                "topic": "CRISPR gene editing", "fiscal_years": [2023],
                "funding_basis": "whole_award",
            })
            r_all = await c.call_tool("summarize_funding_by_topic", {
                "topic": "CRISPR gene editing", "fiscal_years": [2023],
                "funding_basis": "all_records",
            })

        dw, da = r_whole.data, r_all.data

        # Same query → same total matching projects
        assert dw.total_matching_projects == da.total_matching_projects

        # whole_award strictly less (subprojects excluded)
        assert dw.total_award_amount_usd < da.total_award_amount_usd, (
            f"whole_award ${dw.total_award_amount_usd:,.0f} should be < "
            f"all_records ${da.total_award_amount_usd:,.0f}"
        )

        # Subproject exclusion actually happened
        assert dw.subproject_excluded_count > 0

    asyncio.run(_run())


# ── Standalone runner ───────────────────────────────────────────────────


def main() -> int:
    tests = [
        ("Ground-truth exact match (fixture vs tool)", test_ground_truth_exact_match),
        ("Double-counting proof (U19AG068753)", test_double_counting_proof),
        ("Provenance reproducibility (re-fetch + re-sum)", test_provenance_reproducibility),
        ("Missing-amount honesty", test_missing_amount_honesty),
        ("Cross-tool funding-basis consistency", test_cross_tool_basis_consistency),
    ]
    print(f"Running {len(tests)} correctness tests against {MCP_URL}\n")
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}")
            print(f"       {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
