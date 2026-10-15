"""investigator_portfolio — funded portfolio for a named researcher."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import PROJECTS_SEARCH
from nih_reporter_mcp.models import InvestigatorPortfolio
from nih_reporter_mcp.utils import INCLUDE_FIELDS, build_criteria, post_json, to_summary, validate_fiscal_years, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def investigator_portfolio(
        last_name: Annotated[str, Field(description="Investigator's last name, e.g. 'Fauci'.")],
        first_name: Annotated[str | None, Field(description="First name, to narrow a common surname.")] = None,
        fiscal_years: Annotated[list[int] | None, Field(description="Restrict to these fiscal years.")] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="Max projects to return (1-100).")] = 25,
    ) -> InvestigatorPortfolio:
        """Look up the funded research portfolio for a named principal investigator."""
        last_name = validate_topic(last_name)
        fiscal_years = validate_fiscal_years(fiscal_years)

        pi_entry = {"first_name": first_name or "", "last_name": last_name, "any_name": ""}
        payload = {
            "criteria": build_criteria(pi_names=[pi_entry], fiscal_years=fiscal_years),
            "include_fields": INCLUDE_FIELDS,
            "offset": 0,
            "limit": limit,
            "sort_field": "award_amount",
            "sort_order": "desc",
        }
        data = await post_json(PROJECTS_SEARCH, payload)
        total = (data.get("meta") or {}).get("total", 0)
        results = data.get("results") or []
        projects = [to_summary(r) for r in results]
        total_award_returned = sum(p.award_amount or 0 for p in projects)

        note = (f"Showing all {total} matching project(s)." if total <= len(projects) else
                f"Showing the {len(projects)} largest of {total} matching projects.")
        if not first_name:
            note += " No first_name given -- results may include multiple people sharing this surname."

        return InvestigatorPortfolio(
            investigator_query=f"{first_name + ' ' if first_name else ''}{last_name}",
            fiscal_years=fiscal_years, total_matching_projects=total, returned=len(projects),
            truncated=total > len(projects), total_award_amount_usd_returned=round(total_award_returned, 2),
            projects=projects, note=note,
        )
