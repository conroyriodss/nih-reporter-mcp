#!/usr/bin/env python3
"""Standalone smoke-test suite for the NIH RePORTER MCP server.

Runs 17 of the 18 notebook assertions (t1–t8, t10–t18) against a live server.
Test t9 (LLM agent-efficiency regression guard) requires a Databricks
Foundation Model API token and is only available in the companion
notebook (notebook-merged, Cell 12).

Three modes::

    # Quick (~8s) — 5 single-call tests, no full pagination:
    uv run python eval/smoke_tests.py --quick

    # Full parallel (~40s) — all 17 tests run concurrently:
    uv run python eval/smoke_tests.py

    # Full sequential (~100s) — all 17 tests one at a time:
    uv run python eval/smoke_tests.py --sequential

    # Or with a custom server URL:
    MCP_URL=http://localhost:9000/mcp uv run python eval/smoke_tests.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from fastmcp import Client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")

# Tests classified by cost: "quick" are single-call, < 3s each;
# "full" includes multi-page pagination and cross-tool comparisons.
QUICK_TESTS = {"t3", "t5", "t6", "t10", "t13"}

# Per-test timeout (seconds).  Prevents a single slow test from hanging the
# entire suite.  In parallel mode the NIH API is slower under concurrent
# load, so the heavy pagination tests (t1, t2, t14) need more headroom.
# Wall-clock time is bounded by the slowest concurrent test, not the sum.
PER_TEST_TIMEOUT = 90


async def smoke_tests(
    quick: bool = False, sequential: bool = False,
) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    # Deferred tasks for parallel execution
    _deferred: list[tuple[str, str, object]] = []  # (tag, name, coro_fn)

    async def _run_one(tag: str, name: str, coro_fn) -> None:
        """Execute a single test with timeout guard."""
        try:
            ok, detail = await asyncio.wait_for(
                coro_fn(), timeout=PER_TEST_TIMEOUT
            )
            results.append((name, ok, detail))
        except asyncio.TimeoutError:
            results.append((name, False, f"timed out after {PER_TEST_TIMEOUT}s"))
        except Exception as e:
            results.append((name, False, f"raised unexpectedly: {e}"))

    async def check(tag: str, name: str, coro_fn) -> None:
        if quick and tag not in QUICK_TESTS:
            return  # skip expensive tests in quick mode
        if sequential:
            await _run_one(tag, name, coro_fn)
        else:
            _deferred.append((tag, name, coro_fn))

    async with Client(MCP_URL) as c:

        # t1 — Exact-total pagination
        async def t1():
            r = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023]},
            )
            d = r.data
            return (
                d.complete and d.total_matching_projects == 1739,
                f"complete={d.complete}, total={d.total_matching_projects}, "
                f"${d.total_award_amount_usd:,.0f}",
            )
        await check("t1",
            "t1: Exact-total pagination (CRISPR FY2023 == 1,739 matching records)", t1
        )

        # t2 — 10,000-record retrieval cap
        async def t2():
            r = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "cancer", "fiscal_years": [2023], "funding_basis": "all_records"},
            )
            d = r.data
            return (
                not d.complete and d.projects_aggregated == 10000,
                f"complete={d.complete}, aggregated={d.projects_aggregated}, "
                f"total_matching={d.total_matching_projects}",
            )
        await check("t2",
            "t2: 10,000-record retrieval cap honestly flagged (not silently truncated)",
            t2,
        )

        # t3 — Exact org-name match
        async def t3():
            r = await c.call_tool(
                "organization_funding_profile",
                {
                    "organization_name": "BOSTON UNIVERSITY MEDICAL CAMPUS",
                    "fiscal_years": [2024],
                    "exact_match": True,
                },
            )
            d = r.data
            return (
                d.total_matching_projects == 348,
                f"total={d.total_matching_projects} (expected 348)",
            )
        await check("t3",
            "t3: Exact org-name match isolates single institution", t3
        )

        # t4 — RCDC-category vs free-text divergence (both sides fetched live)
        async def t4():
            r_cat = await c.call_tool(
                "summarize_funding_by_topic",
                {"spending_category": "long covid", "fiscal_years": [2023]},
            )
            r_ft = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "long covid", "fiscal_years": [2023]},
            )
            cat_total = r_cat.data.total_award_amount_usd
            ft_total = r_ft.data.total_award_amount_usd
            return (
                50_000_000 < cat_total < 300_000_000
                and ft_total > cat_total,
                f"RCDC-category (live)=${cat_total:,.0f} "
                f"vs free-text (live)=${ft_total:,.0f} "
                f"(ratio={ft_total/cat_total:.1f}x)",
            )
        await check("t4",
            "t4: Live RCDC-category vs free-text: both fetched, divergence confirmed",
            t4,
        )

        # t5 — Empty topic validation
        async def t5():
            try:
                await c.call_tool("search_funded_projects", {"topic": ""})
                return (False, "did not raise")
            except Exception as e:
                return ("empty" in str(e).lower(), str(e)[:100])
        await check("t5",
            "t5: Empty topic raises clean validation error", t5
        )

        # t6 — SQL-injection handling (403 regression)
        async def t6():
            try:
                await c.call_tool(
                    "search_funded_projects",
                    {"topic": 'cancer" OR "1"="1'},
                )
                return (False, "did not raise")
            except Exception as e:
                msg = str(e)
                return (
                    "403" in msg and "httpx" not in msg.lower(),
                    msg[:120],
                )
        await check("t6",
            "t6: SQL-injection-style input: clean 403 handling, no leaked traceback",
            t6,
        )

        # t7 — Cross-tool consistency + whole_award < all_records
        async def t7():
            r1 = await c.call_tool(
                "search_funded_projects",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023], "limit": 1},
            )
            r_whole = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023],
                 "funding_basis": "whole_award"},
            )
            r_all = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023],
                 "funding_basis": "all_records"},
            )
            totals_match = (
                r1.data.total_matching_projects
                == r_whole.data.total_matching_projects
                == r_all.data.total_matching_projects
            )
            whole_lower = (
                r_whole.data.total_award_amount_usd
                < r_all.data.total_award_amount_usd
            )
            return (
                totals_match and whole_lower,
                f"matching={r1.data.total_matching_projects}, "
                f"whole=${r_whole.data.total_award_amount_usd:,.0f} < "
                f"all=${r_all.data.total_award_amount_usd:,.0f}, "
                f"subprojects_excluded={r_whole.data.subproject_excluded_count}",
            )
        await check("t7",
            "t7: Cross-tool consistency + whole_award < all_records (dedup works)",
            t7,
        )

        # t8 — spending_category regression test
        async def t8():
            r = await c.call_tool(
                "funding_trend_by_year",
                {
                    "spending_category": "Cancer",
                    "start_year": 2022,
                    "end_year": 2023,
                },
            )
            d = r.data
            all_nonzero = all(
                y.project_count > 0 and y.total_award_amount_usd > 0
                for y in d.years
            )
            return (
                all_nonzero,
                f"years={[
                    (y.fiscal_year, y.project_count, y.total_award_amount_usd)
                    for y in d.years
                ]}",
            )
        await check("t8",
            "t8: funding_trend_by_year accepts spending_category directly "
            "(regression test for prior bug)",
            t8,
        )

        # t10 — check_investigator_overlap end-to-end
        async def t10():
            r = await c.call_tool(
                "check_investigator_overlap",
                {"last_name": "Collins", "first_name": "Francis"},
            )
            d = r.data
            return (
                isinstance(d.total_active_awards, int)
                and d.total_active_awards >= 0
                and isinstance(d.complete, bool)
                and isinstance(d.total_matching, int)
                and d.total_matching >= d.total_active_awards,
                f"total_active_awards={d.total_active_awards}, "
                f"total_matching={d.total_matching}, "
                f"complete={d.complete}, "
                f"flagged={len(d.flagged_awards)}",
            )
        await check("t10",
            "t10: check_investigator_overlap runs end-to-end, returns "
            "complete/total_matching fields",
            t10,
        )

        # t11 — exclude_project_num logic
        async def t11():
            r1 = await c.call_tool(
                "check_investigator_overlap",
                {"last_name": "Au", "first_name": "Rhoda"},
            )
            r2 = await c.call_tool(
                "check_investigator_overlap",
                {
                    "last_name": "Au",
                    "first_name": "Rhoda",
                    "exclude_project_num": "U19AG068753",
                },
            )
            return (
                r2.data.total_active_awards < r1.data.total_active_awards,
                f"without exclusion: {r1.data.total_active_awards}, "
                f"with exclusion: {r2.data.total_active_awards}",
            )
        await check("t11",
            "t11: exclude_project_num strictly reduces the result count",
            t11,
        )

        # t12 — funded_projects_by_study_section groups and reconciles
        async def t12():
            r = await c.call_tool(
                "funded_projects_by_study_section",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023]},
            )
            d = r.data
            section_sum = sum(s.project_count for s in d.sections)
            return (
                len(d.sections) > 0 and section_sum <= d.total_projects,
                f"sections={len(d.sections)}, "
                f"section_project_sum={section_sum}, "
                f"total_projects={d.total_projects}",
            )
        await check("t12",
            "t12: funded_projects_by_study_section groups projects correctly, "
            "counts reconcile",
            t12,
        )

        # t13 — search_recent_awards returns results sorted by date_added
        async def t13():
            r = await c.call_tool(
                "search_recent_awards", {"limit": 5},
            )
            d = r.data
            has_awards = len(d.awards) > 0
            respects_limit = d.returned > 0 and d.returned <= 5
            all_have_url = all(hasattr(a, 'reporter_url') and a.reporter_url for a in d.awards)
            return (
                has_awards and respects_limit and all_have_url,
                f"returned={d.returned}, "
                f"total_matching={d.total_matching}, "
                f"has_awards={has_awards}, all_have_url={all_have_url}",
            )
        await check("t13",
            "t13: search_recent_awards returns valid results respecting limit",
            t13,
        )

        # t14 — provenance populated and counting-unit trap documented
        async def t14():
            r = await c.call_tool(
                "summarize_funding_by_topic",
                {
                    "topic": "CRISPR gene editing",
                    "fiscal_years": [2023],
                    "include_provenance": True,
                },
            )
            d = r.data
            has_prov = d.provenance is not None
            basis_stated = "whole_award" in d.counting_unit.lower() or "whole_award" in d.funding_basis
            agg = d.provenance.records_aggregated if has_prov else 0
            sub_excl = d.subproject_excluded_count
            return (
                has_prov and basis_stated and agg >= 1400 and sub_excl > 0,
                f"provenance={has_prov}, "
                f"basis={d.funding_basis}, "
                f"aggregated={agg}, subproject_excluded={sub_excl}",
            )
        await check("t14",
            "t14: Provenance populated and counting-unit trap documented",
            t14,
        )

        # t15 — export_evidence_bundle returns inspectable source record IDs
        async def t15():
            r = await c.call_tool(
                "export_evidence_bundle",
                {
                    "topic": "sickle cell disease",
                    "fiscal_years": [2023],
                    "label": "SCD FY23",
                },
            )
            d = r.data
            has_ids = len(d.provenance.source_record_ids) > 0
            has_repro = "reproduce" in d.reproduction_note.lower()
            return (
                has_ids and has_repro,
                f"source_ids={len(d.provenance.source_record_ids)}, "
                f"has_repro_note={has_repro}",
            )
        await check("t15",
            "t15: export_evidence_bundle returns inspectable source record IDs",
            t15,
        )

        # t16 — explain_health_topic returns a MedlinePlus summary
        async def t16():
            r = await c.call_tool(
                "explain_health_topic", {"topic": "diabetes"},
            )
            d = r.data
            return (
                d.found and d.summary is not None and len(d.summary) > 50,
                f"found={d.found}, "
                f"summary_len={len(d.summary) if d.summary else 0}",
            )
        await check("t16",
            "t16: explain_health_topic returns a MedlinePlus summary "
            "for a common condition",
            t16,
        )

        # t17 — explain_health_topic handles no-match cleanly
        async def t17():
            r = await c.call_tool(
                "explain_health_topic",
                {"topic": "zzznotarealcondition999"},
            )
            d = r.data
            return (
                d.found is False and "no" in d.note.lower(),
                f"found={d.found}, note={d.note[:80]}",
            )
        await check("t17",
            "t17: explain_health_topic handles no-match cleanly "
            "(not an error)",
            t17,
        )

        # t18 — Cache correctness: whole_award vs all_records never collide
        async def t18():
            import time as _t
            w1 = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023],
                 "funding_basis": "whole_award"},
            )
            a1 = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023],
                 "funding_basis": "all_records"},
            )
            t0 = _t.monotonic()
            w2 = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023],
                 "funding_basis": "whole_award"},
            )
            warm_lat = _t.monotonic() - t0
            whole_stable = (
                w1.data.total_award_amount_usd == w2.data.total_award_amount_usd
            )
            bases_differ = (
                w1.data.total_award_amount_usd != a1.data.total_award_amount_usd
            )
            return (
                whole_stable and bases_differ,
                f"whole_award stable={whole_stable}, "
                f"whole!=all_records={bases_differ} "
                f"(${w1.data.total_award_amount_usd:,.0f} vs "
                f"${a1.data.total_award_amount_usd:,.0f}), "
                f"warm_latency={warm_lat:.2f}s",
            )
        await check("t18",
            "t18: Cache preserves correctness and never collides "
            "whole_award with all_records",
            t18,
        )

        # --- parallel execution: fire all deferred tests concurrently ---
        if _deferred:
            await asyncio.gather(
                *(_run_one(tag, name, fn) for tag, name, fn in _deferred)
            )
            # Sort results back into tag order for deterministic output
            tag_order = [name for _, name, _ in _deferred]
            results.sort(
                key=lambda r: tag_order.index(r[0]) if r[0] in tag_order else 999
            )

    return results


def main() -> int:
    quick = "--quick" in sys.argv
    seq = "--sequential" in sys.argv
    mode = "QUICK" if quick else ("FULL (sequential)" if seq else "FULL (parallel)")
    print(f"Running {mode} smoke tests against {MCP_URL}\n")
    results = asyncio.run(smoke_tests(quick=quick, sequential=seq))

    print("\n" + "=" * 78)
    print("SMOKE TEST RESULTS")
    print("=" * 78)
    passed = 0
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"[{mark}] {name}")
        print(f"       {detail}")
    print("-" * 78)
    print(f"TOTAL: {passed}/{len(results)} passed")
    if passed < len(results):
        print(
            "\nNote: t9 (LLM agent-efficiency regression guard) is only "
            "available in the companion notebook (requires Databricks "
            "Foundation Model API access)."
        )
    print("=" * 78)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
