from __future__ import annotations

from collections import defaultdict
from typing import Annotated

from pydantic import BaseModel, Field
from fastmcp import FastMCP

from nih_reporter_mcp.utils import (
    validate_fiscal_years,
    validate_topic,
    paginate_all,
    build_criteria,
    aggregate_funding,
)


class StudySectionSummary(BaseModel):
    srg_code: str | None
    study_section_name: str | None
    project_count: int
    total_award_amount_usd: float
    distinct_ics: list[str]


class StudySectionWorkloadResult(BaseModel):
    fiscal_years: list[int] | None
    topic_filter: str | None
    total_projects: int
    complete: bool
    sections: list[StudySectionSummary]
    note: str


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def study_section_workload(
        fiscal_years: Annotated[
            list[int] | None,
            Field(
                description=(
                    "Fiscal years to analyze. Strongly recommended to narrow scope."
                )
            ),
        ] = None,
        topic: Annotated[
            str | None,
            Field(
                description=(
                    "Optional topic/keyword filter, to see funded-project "
                    "distribution by study section for a specific research area."
                )
            ),
        ] = None,
        agencies: Annotated[
            list[str] | None,
            Field(
                description="Limit to specific administering IC abbreviations."
            ),
        ] = None,
    ) -> StudySectionWorkloadResult:
        """Summarize the distribution of funded projects across scientific
        review study sections -- the peer-review panels that evaluated the
        funded applications.

        SCOPE LIMITATION: This shows funded outcomes only (awards that
        received funding). It does NOT reflect the full review workload of
        a study section, since unfunded and pending applications are not in
        RePORTER. Useful for seeing which study sections handle funded
        projects in a research area, but not for inferring review volume,
        success rates, or panel workload. Aggregates by paginating all
        matching projects (subject to the same 10,000-record retrieval cap
        as other tools here) and grouping client-side by study section,
        since RePORTER's API does not offer native server-side aggregation
        by this field.
        """
        if topic:
            topic = validate_topic(topic)
        fiscal_years = validate_fiscal_years(fiscal_years)

        base_payload = {
            "criteria": build_criteria(
                topic=topic, fiscal_years=fiscal_years, agencies=agencies
            ),
            "include_fields": [
                "ApplId",
                "SubprojectId",
                "AwardAmount",
                "FullStudySection",
                "AgencyIcAdmin",
            ],
        }
        results, total, complete, _pf, _ids = await paginate_all(base_payload)

        groups_raw: dict[tuple, list[dict]] = defaultdict(list)
        no_section_count = 0

        for r in results:
            section = r.get("full_study_section")
            if not section:
                no_section_count += 1
                continue
            key = (section.get("srg_code"), section.get("name"))
            groups_raw[key].append(r)

        sections = []
        for k, group_records in groups_raw.items():
            agg = aggregate_funding(group_records, funding_basis="whole_award")
            ics = {
                (r.get("agency_ic_admin") or {}).get("abbreviation")
                for r in group_records
                if (r.get("agency_ic_admin") or {}).get("abbreviation")
            }
            sections.append(
                StudySectionSummary(
                    srg_code=k[0],
                    study_section_name=k[1],
                    project_count=agg.record_count,
                    total_award_amount_usd=agg.total_award,
                    distinct_ics=sorted(ics),
                )
            )
        sections.sort(key=lambda s: s.total_award_amount_usd, reverse=True)

        note = (
            "Totals cover all matching projects."
            if complete
            else (
                "Hit the pagination safety cap; totals are a partial lower "
                "bound -- narrow by fiscal_years for an exact figure."
            )
        )
        if no_section_count:
            note += (
                f" {no_section_count} matching project(s) had no study "
                "section on record (e.g. some intramural/contract mechanisms "
                "don't use standard peer review) and are excluded from the "
                "breakdown."
            )

        return StudySectionWorkloadResult(
            fiscal_years=fiscal_years,
            topic_filter=topic,
            total_projects=total,
            complete=complete,
            sections=sections,
            note=note,
        )
