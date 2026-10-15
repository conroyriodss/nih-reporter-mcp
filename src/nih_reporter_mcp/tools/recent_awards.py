from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field
from fastmcp import FastMCP

from nih_reporter_mcp.models import ProjectSummary
from nih_reporter_mcp.utils import (
    validate_topic,
    validate_state,
    post_json,
    to_summary,
    build_criteria,
    INCLUDE_FIELDS,
)
from nih_reporter_mcp.config import PROJECTS_SEARCH


class RecentAwardsResult(BaseModel):
    topic_filter: str | None
    returned: int
    total_matching: int
    truncated: bool
    awards: list[ProjectSummary]
    note: str


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def search_recent_awards(
        topic: Annotated[
            str | None,
            Field(
                description=(
                    "Optional topic/keyword filter to narrow to a specific "
                    "research area. Omit to see all recently added NIH/HHS awards."
                )
            ),
        ] = None,
        org_state: Annotated[
            str | None,
            Field(description="Optional two-letter state filter."),
        ] = None,
        agencies: Annotated[
            list[str] | None,
            Field(description="Optional administering IC filter."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Max awards to return (1-100)."),
        ] = 25,
    ) -> RecentAwardsResult:
        """Find the most recently added NIH/HHS award records, sorted by
        date added to RePORTER (not award/start date).

        Useful for program officers tracking what's newly funded in their
        portfolio. NOTE: 'recently added to RePORTER' can lag the actual
        award notice date, since RePORTER data refreshes periodically
        rather than in real time -- this reflects database recency, not
        necessarily award recency. For award-date-based recency, use
        search_funded_projects with sort_by_award and appropriate
        fiscal_years instead.
        """
        if topic:
            topic = validate_topic(topic)
        org_state = validate_state(org_state)

        payload = {
            "criteria": build_criteria(
                topic=topic, org_state=org_state, agencies=agencies,
            ),
            "include_fields": INCLUDE_FIELDS + ["DateAdded", "IsNew"],
            "offset": 0,
            "limit": limit,
            "sort_field": "date_added",
            "sort_order": "desc",
        }
        data = await post_json(PROJECTS_SEARCH, payload)
        total = (data.get("meta") or {}).get("total", 0)
        results = data.get("results") or []
        awards = [to_summary(r) for r in results]

        note = (
            f"Showing all {total} matching award(s)."
            if total <= len(awards)
            else f"Showing the {len(awards)} most recently added of "
            f"{total} matching awards."
        )
        note += (
            " 'Recently added' reflects RePORTER's database refresh "
            "schedule, not necessarily the actual award notice date."
        )

        return RecentAwardsResult(
            topic_filter=topic,
            returned=len(awards),
            total_matching=total,
            truncated=total > len(awards),
            awards=awards,
            note=note,
        )
