"""funding_trend_by_year — year-by-year funding trend for a topic or spending category."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import resolve_spending_category
from nih_reporter_mcp.models import FundingTrend, YearFunding
from nih_reporter_mcp.utils import build_criteria, paginate_all, validate_fiscal_years, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def funding_trend_by_year(
        start_year: Annotated[int, Field(description="First fiscal year to include.")],
        end_year: Annotated[int, Field(description="Last fiscal year to include.")],
        topic: Annotated[str | None, Field(description="Research topic or keywords, e.g. 'long COVID'. Omit if using spending_category instead.")] = None,
        agencies: Annotated[list[str] | None, Field(description="Limit to agency/IC abbreviations.")] = None,
        spending_category: Annotated[str | int | None, Field(description="NIH official RCDC spending category -- name (e.g. 'Cancer', 'Long COVID') or numeric ID. More authoritative than free-text for official totals.")] = None,
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

        year_results = []
        any_incomplete = False
        for year in years:
            base_payload = {
                "criteria": build_criteria(
                    topic=topic, fiscal_years=[year], agencies=agencies,
                    spending_categories=[category_id] if category_id else None,
                ),
                "include_fields": ["AwardAmount"],
            }
            results, total, complete = await paginate_all(base_payload)
            if not complete:
                any_incomplete = True
            total_award = sum(r.get("award_amount") or 0 for r in results)
            year_results.append(YearFunding(
                fiscal_year=year, project_count=total,
                total_award_amount_usd=round(total_award, 2), complete=complete,
            ))

        note = ("All years aggregated exactly." if not any_incomplete else
                "One or more years hit the pagination safety cap; see per-year 'complete' flags.")
        return FundingTrend(
            topic=topic or f"spending_category:{spending_category}",
            years=year_results, note=note,
        )
