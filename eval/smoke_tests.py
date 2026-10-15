#!/usr/bin/env python3
"""Standalone smoke-test suite for the NIH RePORTER MCP server.

Runs 8 of the 9 notebook assertions (t1–t8) against a live server.
Test t9 (LLM agent-efficiency regression guard) requires a Databricks
Foundation Model API token and is only available in the companion
notebook (notebook-merged, Cell 12).

Usage::

    # Start the server first:
    uv run python main.py &
    sleep 5

    # Run the suite:
    uv run python eval/smoke_tests.py

    # Or with a custom server URL:
    MCP_URL=http://localhost:9000/mcp uv run python eval/smoke_tests.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from fastmcp import Client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")


async def smoke_tests() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    async def check(name: str, coro_fn) -> None:
        try:
            ok, detail = await coro_fn()
            results.append((name, ok, detail))
        except Exception as e:
            results.append((name, False, f"raised unexpectedly: {e}"))

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
        await check(
            "t1: Exact-total pagination (CRISPR FY2023 == 1,739 projects)", t1
        )

        # t2 — 10,000-record ceiling
        async def t2():
            r = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "cancer", "fiscal_years": [2023]},
            )
            d = r.data
            return (
                not d.complete and d.projects_aggregated == 10000,
                f"complete={d.complete}, aggregated={d.projects_aggregated}, "
                f"total_matching={d.total_matching_projects}",
            )
        await check(
            "t2: 10,000-record ceiling honestly flagged (not silently truncated)",
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
        await check(
            "t3: Exact org-name match isolates single institution", t3
        )

        # t4 — RCDC vs free-text divergence
        async def t4():
            r = await c.call_tool(
                "summarize_funding_by_topic",
                {"spending_category": "long covid", "fiscal_years": [2023]},
            )
            d = r.data
            return (
                d.total_award_amount_usd < 300_000_000,
                f"RCDC category total=${d.total_award_amount_usd:,.0f} "
                f"vs free-text total=$891,742,057 (same query)",
            )
        await check(
            "t4: Official RCDC category vs free-text search: documented divergence",
            t4,
        )

        # t5 — Empty topic validation
        async def t5():
            try:
                await c.call_tool("search_funded_projects", {"topic": ""})
                return (False, "did not raise")
            except Exception as e:
                return ("empty" in str(e).lower(), str(e)[:100])
        await check(
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
        await check(
            "t6: SQL-injection-style input: clean 403 handling, no leaked traceback",
            t6,
        )

        # t7 — Cross-tool consistency
        async def t7():
            r1 = await c.call_tool(
                "search_funded_projects",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023], "limit": 1},
            )
            r2 = await c.call_tool(
                "summarize_funding_by_topic",
                {"topic": "CRISPR gene editing", "fiscal_years": [2023]},
            )
            match = (
                r1.data.total_matching_projects
                == r2.data.total_matching_projects
            )
            return (
                match,
                f"{r1.data.total_matching_projects} vs "
                f"{r2.data.total_matching_projects}",
            )
        await check(
            "t7: Cross-tool consistency (search vs summarize agree on totals)",
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
        await check(
            "t8: funding_trend_by_year accepts spending_category directly "
            "(regression test for prior bug)",
            t8,
        )

    return results


def main() -> int:
    print(f"Running smoke tests against {MCP_URL}\n")
    results = asyncio.run(smoke_tests())

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
