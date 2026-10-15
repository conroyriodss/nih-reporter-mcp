from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field
from fastmcp import FastMCP

from nih_reporter_mcp.models import ProjectSummary
from nih_reporter_mcp.utils import (
    validate_topic,
    validate_string_length,
    validate_fiscal_years,
    post_json,
    to_summary,
    build_criteria,
    INCLUDE_FIELDS,
)
from nih_reporter_mcp.config import PROJECTS_SEARCH


class OverlapFlag(BaseModel):
    project: ProjectSummary
    overlap_reason: str = Field(
        ...,
        description=(
            "Why this project was flagged: 'currently active', "
            "'same fiscal year as excluded project', etc."
        ),
    )


class OverlapCheckResult(BaseModel):
    investigator_query: str
    exclude_project_num: str | None
    total_active_awards: int
    flagged_awards: list[OverlapFlag]
    all_active_awards: list[ProjectSummary]
    note: str


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def check_investigator_overlap(
        last_name: Annotated[
            str, Field(description="Investigator's last name.")
        ],
        first_name: Annotated[
            str | None,
            Field(
                description=(
                    "First name, strongly recommended to avoid false matches "
                    "on common surnames."
                )
            ),
        ] = None,
        exclude_project_num: Annotated[
            str | None,
            Field(
                description=(
                    "A core project number to exclude from results (e.g. the "
                    "application currently under review), so overlap is assessed "
                    "against OTHER awards only."
                )
            ),
        ] = None,
        as_of_fiscal_year: Annotated[
            int | None,
            Field(
                description=(
                    "Fiscal year to assess 'currently active' against. Defaults "
                    "to the most recent fiscal year with data if omitted."
                )
            ),
        ] = None,
    ) -> OverlapCheckResult:
        """Screen an investigator's publicly funded NIH awards for candidate
        overlap, as a starting point for Other Support review.

        SCOPE LIMITATION: This searches only publicly visible funded awards
        in RePORTER. It cannot see pending applications, non-NIH/non-HHS
        support, or unpublished awards. It is a public-record screening tool,
        not a complete Other Support determination.

        Returns all currently active awards for the named investigator,
        explicitly excluding a given project number (typically the
        application under review), flagged by why each might represent
        overlapping support. This does NOT determine actual duplication --
        it surfaces candidates for a human reviewer to examine, since true
        overlap determination requires comparing scientific aims, which
        this tool cannot assess from funding records alone.
        """
        last_name = validate_topic(last_name)
        if first_name:
            first_name = validate_string_length(first_name, "first_name")
        if exclude_project_num:
            exclude_project_num = validate_string_length(
                exclude_project_num, "exclude_project_num",
            )
        fiscal_years = (
            validate_fiscal_years([as_of_fiscal_year])
            if as_of_fiscal_year
            else None
        )

        pi_entry = {
            "first_name": first_name or "",
            "last_name": last_name,
            "any_name": "",
        }
        payload = {
            "criteria": build_criteria(
                pi_names=[pi_entry], fiscal_years=fiscal_years
            ),
            "include_fields": INCLUDE_FIELDS
            + ["IsActive", "ProjectStartDate", "ProjectEndDate"],
            "offset": 0,
            "limit": 100,
            "sort_field": "project_start_date",
            "sort_order": "desc",
        }
        data = await post_json(PROJECTS_SEARCH, payload)
        results = data.get("results") or []

        active = [
            r
            for r in results
            if r.get("is_active") is True
            and r.get("core_project_num") != exclude_project_num
        ]

        flagged = []
        for r in active:
            summary = to_summary(r)
            flagged.append(
                OverlapFlag(
                    project=summary,
                    overlap_reason=(
                        "Currently active award"
                        + (
                            f" in FY{as_of_fiscal_year}"
                            if as_of_fiscal_year
                            else ""
                        )
                    ),
                )
            )

        note = (
            f"Found {len(active)} currently active award(s) for this investigator"
            + (
                f", excluding {exclude_project_num}"
                if exclude_project_num
                else ""
            )
            + ". This tool surfaces candidate overlapping support for human review; "
            "it does NOT determine actual scientific or budgetary duplication. "
            "Cross-reference award dates, direct costs, and specific aims manually. "
            "If no first_name was given, results may include multiple people "
            "sharing this surname -- verify identity before using for compliance "
            "review."
        )
        if not first_name:
            note += (
                " WARNING: no first_name provided; false-positive risk is elevated."
            )

        return OverlapCheckResult(
            investigator_query=(
                f"{first_name + ' ' if first_name else ''}{last_name}"
            ),
            exclude_project_num=exclude_project_num,
            total_active_awards=len(active),
            flagged_awards=flagged,
            all_active_awards=[to_summary(r) for r in active],
            note=note,
        )
