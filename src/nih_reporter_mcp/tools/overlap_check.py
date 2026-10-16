from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field
from fastmcp import FastMCP

from nih_reporter_mcp.models import ProjectSummary
from nih_reporter_mcp.utils import (
    validate_topic,
    validate_string_length,
    validate_fiscal_years,
    to_summary,
    build_criteria,
    paginate_all,
    INCLUDE_FIELDS,
)


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
    total_matching: int = Field(
        description="Total matching records reported by the upstream API.",
    )
    complete: bool = Field(
        description=(
            "True when every matching record was retrieved and examined. "
            "False when retrieval was truncated by the API's record ceiling."
        ),
    )
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
        """Active public-award inventory for overlap screening — lists an
        investigator's currently active NIH awards as a starting point for
        Other Support review.

        SCOPE LIMITATION: This is a public-record screening tool, NOT a
        scientific-overlap or complete Other-Support determination.  It
        searches only publicly visible funded awards in RePORTER. It cannot
        see pending applications, non-NIH/non-HHS support, or unpublished
        awards.

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
        base_payload = {
            "criteria": build_criteria(
                pi_names=[pi_entry], fiscal_years=fiscal_years
            ),
            "include_fields": INCLUDE_FIELDS
            + ["IsActive", "ProjectStartDate", "ProjectEndDate"],
            "sort_field": "project_start_date",
            "sort_order": "desc",
        }
        results, total, complete, _pages, _ids = await paginate_all(
            base_payload
        )

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

        note_parts = [
            f"Found {len(active)} currently active award(s) for this investigator",
        ]
        if exclude_project_num:
            note_parts[0] += f", excluding {exclude_project_num}"
        note_parts[0] += "."

        if not complete:
            note_parts.append(
                f"WARNING: only {len(results)} of {total} matching records "
                "could be retrieved (RePORTER retrieval ceiling). The true "
                "active-award count may be higher — narrow the query "
                "(e.g. add fiscal year or first name) for completeness."
            )

        note_parts.append(
            "This tool surfaces candidate overlapping support for human review; "
            "it does NOT determine actual scientific or budgetary duplication. "
            "Cross-reference award dates, direct costs, and specific aims manually. "
            "If no first_name was given, results may include multiple people "
            "sharing this surname -- verify identity before using for compliance "
            "review."
        )
        if not first_name:
            note_parts.append(
                "WARNING: no first_name provided; false-positive risk is elevated."
            )
        note = " ".join(note_parts)

        return OverlapCheckResult(
            investigator_query=(
                f"{first_name + ' ' if first_name else ''}{last_name}"
            ),
            exclude_project_num=exclude_project_num,
            total_matching=total,
            complete=complete,
            total_active_awards=len(active),
            flagged_awards=flagged,
            all_active_awards=[to_summary(r) for r in active],
            note=note,
        )
