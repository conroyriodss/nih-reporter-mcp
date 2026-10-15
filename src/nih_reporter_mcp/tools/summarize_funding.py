"""summarize_funding_by_topic — exact total investment via full pagination."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import MAX_RESULT_SET, PAGE_SIZE, resolve_spending_category
from nih_reporter_mcp.models import FundingSummary
from nih_reporter_mcp.utils import AGG_FIELDS, build_criteria, paginate_all, validate_fiscal_years, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def summarize_funding_by_topic(
        topic: Annotated[str | None, Field(description="Research topic or keywords to total funding for. Omit if using spending_category instead.")] = None,
        fiscal_years: Annotated[list[int] | None, Field(description="Fiscal years to include, e.g. [2022, 2023, 2024].")] = None,
        agencies: Annotated[list[str] | None, Field(description="Limit to agency/IC abbreviations, e.g. ['NCI'].")] = None,
        spending_category: Annotated[str | int | None, Field(description="NIH official RCDC spending category -- name (e.g. 'Alzheimer's Disease', 'Cancer', 'Long COVID') or numeric ID. More authoritative than free-text for official totals.")] = None,
        active_only: Annotated[bool | None, Field(description="If true, active projects only (client-side filtered). If false, inactive only. Omit for all.")] = None,
    ) -> FundingSummary:
        """Quantify total NIH/HHS investment in a research topic (oversight view).
        Paginates through ALL matching projects (up to 10,000) for an exact total."""
        if not topic and not spending_category:
            raise ValueError("Provide at least one of topic or spending_category.")
        if topic:
            topic = validate_topic(topic)
        fiscal_years = validate_fiscal_years(fiscal_years)
        category_id = resolve_spending_category(spending_category) if spending_category else None

        base_payload = {
            "criteria": build_criteria(
                topic=topic, fiscal_years=fiscal_years, agencies=agencies,
                spending_categories=[category_id] if category_id else None,
            ),
            "include_fields": AGG_FIELDS + (["IsActive"] if active_only is not None else []),
            "sort_field": "award_amount",
            "sort_order": "desc",
        }
        results, total, complete = await paginate_all(base_payload)

        if active_only is not None:
            results = [r for r in results if r.get("is_active") == active_only]

        total_award = sum(r.get("award_amount") or 0 for r in results)
        orgs = {(r.get("organization") or {}).get("org_name") for r in results if (r.get("organization") or {}).get("org_name")}
        ics = {(r.get("agency_ic_admin") or {}).get("abbreviation") for r in results if (r.get("agency_ic_admin") or {}).get("abbreviation")}
        pages_fetched = (len(results) + PAGE_SIZE - 1) // PAGE_SIZE if results else 0

        note = ("Total is exact: every matching project was aggregated." if complete else
                f"Only the top {len(results)} of {total} matching projects were aggregated "
                f"(hit RePORTER's {MAX_RESULT_SET}-record retrieval ceiling). Narrow the query for an exact figure.")
        if active_only is None:
            note += " Includes both active and expired/inactive projects across all time."
        else:
            note += f" Filtered client-side to active_only={active_only}; total_matching_projects is the unfiltered count."

        return FundingSummary(
            topic=topic or f"spending_category:{spending_category}",
            fiscal_years=fiscal_years, total_matching_projects=total, projects_aggregated=len(results),
            complete=complete, total_award_amount_usd=round(total_award, 2),
            distinct_organizations=len(orgs), distinct_administering_ics=len(ics),
            pages_fetched=pages_fetched, note=note,
        )
