"""funding_trend_by_year — year-by-year funding trend for a topic or spending category."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import resolve_spending_category
from nih_reporter_mcp.models import FundingTrend, YearFunding
from nih_reporter_mcp.utils import AGG_FIELDS, aggregate_funding, build_criteria, paginate_all, validate_fiscal_years, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def funding_trend_by_year(
        start_year: Annotated[int, Field(description="First fiscal year to include.")],
        end_year: Annotated[int, Field(description="Last fiscal year to include.")],
        topic: Annotated[str | None, Field(description="Research topic or keywords, e.g. 'long COVID'. Omit if using spending_category instead.")] = None,
        agencies: Annotated[list[str] | None, Field(description="Limit to agency/IC abbreviations.")] = None,
        spending_category: Annotated[str | int | None, Field(description="NIH official RCDC spending category -- name (e.g. 'Cancer', 'Long COVID') or numeric ID. More authoritative than free-text for official totals.")] = None,
        funding_basis: Annotated[str, Field(description="'whole_award' (default) or 'all_records'.")] = "whole_award",
    ) -> FundingTrend:
        """Show NIH/HHS funding for a topic (or official spending category) broken out year by year."""
        if not topic and not spending_category:
            raise ValueError("Provide at least one of topic or spending_category.")
        if topic:
            topic = validate_topic(topic)
        category_id = resolve_spending_category(spending_category) if spending_category else None
        years = validate_fiscal_years(list(range(start_year, end_year + 1)))
        if len(years) > 15:
            raise ValueError("Range too wide (max 15 fiscal years per call) to keep response times reasonable.")

        if funding_basis not in ("whole_award", "all_records"):
            raise ValueError("funding_basis must be 'whole_award' or 'all_records'.")

        async def _fetch_year(year: int) -> YearFunding:
            base_payload = {
                "criteria": build_criteria(
                    topic=topic, fiscal_years=[year], agencies=agencies,
                    spending_categories=[category_id] if category_id else None,
                ),
                "include_fields": AGG_FIELDS,
            }
            results, total, complete, _pf, _ids = await paginate_all(base_payload)
            agg = aggregate_funding(results, funding_basis=funding_basis)
            return YearFunding(
                fiscal_year=year, project_count=agg.record_count,
                total_award_amount_usd=agg.total_award, complete=complete,
                records_with_missing_amount=agg.records_with_missing_amount,
            )

        # Fire all years concurrently — the rate limiter in post_json still
        # serialises upstream HTTP calls to ~1 req/sec on cache misses while
        # cache hits resolve instantly.
        year_results_raw = await asyncio.gather(
            *(_fetch_year(y) for y in years), return_exceptions=True,
        )
        year_results = []
        any_incomplete = False
        for yr in year_results_raw:
            if isinstance(yr, Exception):
                raise yr
            year_results.append(yr)
            if not yr.complete:
                any_incomplete = True

        any_missing = any(yr.records_with_missing_amount > 0 for yr in year_results)
        note_parts = []
        if any_incomplete:
            note_parts.append(
                "One or more years hit the pagination safety cap; "
                "see per-year 'complete' flags."
            )
        if any_missing:
            note_parts.append(
                "One or more years had records with missing award amounts "
                "(see per-year records_with_missing_amount); totals for "
                "those years are not exact."
            )
        if not note_parts:
            note_parts.append("All years aggregated exactly.")
        note = " ".join(note_parts)
        return FundingTrend(
            topic=topic or f"spending_category:{spending_category}",
            years=year_results, note=note,
        )
