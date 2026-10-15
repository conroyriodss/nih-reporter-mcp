"""search_funded_projects — find funded projects on a topic, with filters."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import PROJECTS_SEARCH
from nih_reporter_mcp.models import SearchResult
from nih_reporter_mcp.utils import (
    INCLUDE_FIELDS,
    build_criteria,
    post_json,
    to_summary,
    validate_fiscal_years,
    validate_state,
    validate_topic,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def search_funded_projects(
        topic: Annotated[str, Field(description=(
            "Research topic or keywords to search across all project text fields "
            "(title, abstract, terms), e.g. 'Alzheimer's biomarkers'. RePORTER's "
            "search already handles singular/plural and minor phrasing variants "
            "internally -- retrying with near-identical rephrasings (e.g. singular "
            "vs plural, or adding '*' wildcards) will NOT change results, so do not "
            "repeat a query that returned 0 or few results with only minor wording "
            "changes. If results seem incomplete, instead broaden by removing a "
            "qualifying word (e.g. 'Alzheimer's biomarkers' -> 'Alzheimer's') or "
            "widen fiscal_years, rather than rephrasing the same concept."
        ))],
        fiscal_years: Annotated[list[int] | None, Field(description="Restrict to these fiscal years, e.g. [2023, 2024].")] = None,
        org_state: Annotated[str | None, Field(description="Two-letter US state of the recipient organization, e.g. 'MA'.")] = None,
        agencies: Annotated[list[str] | None, Field(description="Administering agency/IC abbreviations, e.g. ['NIGMS', 'NIAID'].")] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="Max projects to return (1-100).")] = 25,
        sort_by_award: Annotated[bool, Field(description="If true, return the largest awards first.")] = True,
        active_only: Annotated[bool | None, Field(description="If true, restrict to currently active projects only, filtered client-side. If false, only inactive/expired. Omit for both.")] = None,
    ) -> SearchResult:
        """Find NIH/HHS-funded research projects matching a topic."""
        topic = validate_topic(topic)
        fiscal_years = validate_fiscal_years(fiscal_years)
        org_state = validate_state(org_state)

        payload = {
            "criteria": build_criteria(topic=topic, fiscal_years=fiscal_years, org_state=org_state, agencies=agencies),
            "include_fields": INCLUDE_FIELDS + (["IsActive"] if active_only is not None else []),
            "offset": 0,
            "limit": limit if active_only is None else min(limit * 3, 500),
        }
        if sort_by_award:
            payload["sort_field"] = "award_amount"
            payload["sort_order"] = "desc"

        data = await post_json(PROJECTS_SEARCH, payload)
        total = (data.get("meta") or {}).get("total", 0)
        results = data.get("results") or []
        if active_only is not None:
            results = [r for r in results if r.get("is_active") == active_only][:limit]
        projects = [to_summary(r) for r in results]
        return SearchResult(
            total_matching_projects=total, returned=len(projects),
            truncated=total > len(projects), projects=projects,
        )
