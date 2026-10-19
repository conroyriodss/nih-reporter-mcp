"""search_funded_projects — find funded projects on a topic, with filters."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import PROJECTS_SEARCH
from nih_reporter_mcp.models import GroupByBucket, GroupByResult, SearchResult
from nih_reporter_mcp.utils import (
    AGG_FIELDS,
    INCLUDE_FIELDS,
    build_criteria,
    paginate_all,
    post_json,
    to_summary,
    validate_fiscal_years,
    validate_list_length,
    validate_state,
    validate_topic,
)

_GROUP_BY_FIELDS = {
    "organization": lambda r: (r.get("organization") or {}).get("org_name") or "Unknown",
    "activity_code": lambda r: r.get("activity_code") or "Unknown",
    "org_state": lambda r: (r.get("organization") or {}).get("org_state") or "Unknown",
    "administering_ic": lambda r: (r.get("agency_ic_admin") or {}).get("abbreviation") or "Unknown",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def search_funded_projects(
        topic: Annotated[str | None, Field(description=(
            "Research topic or keywords to search across all project text fields "
            "(title, abstract, terms), e.g. 'Alzheimer\'s biomarkers'. RePORTER's "
            "search already handles singular/plural and minor phrasing variants "
            "internally -- retrying with near-identical rephrasings (e.g. singular "
            "vs plural, or adding '*' wildcards) will NOT change results, so do not "
            "repeat a query that returned 0 or few results with only minor wording "
            "changes. If results seem incomplete, instead broaden by removing a "
            "qualifying word (e.g. 'Alzheimer\'s biomarkers' -> 'Alzheimer\'s') or "
            "widen fiscal_years, rather than rephrasing the same concept."
        ))] = None,
        fiscal_years: Annotated[list[int] | None, Field(description="Restrict to these fiscal years, e.g. [2023, 2024].")] = None,
        org_state: Annotated[str | None, Field(description="Two-letter US state of the recipient organization, e.g. 'MA'.")] = None,
        agencies: Annotated[list[str] | None, Field(description="Administering agency/IC abbreviations, e.g. ['NIGMS', 'NIAID'].")] = None,
        activity_codes: Annotated[list[str] | None, Field(description=(
            "NIH activity codes (grant mechanism types) to filter by, e.g. ['R01'], ['R01', 'R21'], ['U01']. "
            "Use this for mechanism-specific questions like 'how many R01 awards' or 'K-series grants'. "
            "Do NOT put activity codes in the topic field — topic is for research subject text search, "
            "activity_codes is for structural grant-type filtering. Common codes: "
            "R01 (research project), R21 (exploratory), R43/R44 (SBIR), U01 (cooperative), "
            "P01/P30/P50 (program/center), T32 (training), F31/F32 (fellowship), "
            "K01/K08/K23/K99 (career development)."
        ))] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="Max projects to return (1-100).")] = 25,
        sort_by_award: Annotated[bool, Field(description="If true, return the largest awards first.")] = True,
        active_only: Annotated[bool | None, Field(description="If true, restrict to currently active projects only, filtered client-side. If false, only inactive/expired. Omit for both.")] = None,
        group_by: Annotated[str | None, Field(description=(
            "Instead of listing individual projects, GROUP results by this dimension "
            "and return a RANKED table of (key, project_count, total_award). "
            "Use this for 'which institution/state/IC got the most' questions. "
            "Valid values: 'organization', 'activity_code', 'org_state', 'administering_ic'. "
            "When group_by is set, the tool paginates the FULL matching cohort "
            "(up to 10,000 records) and returns the top groups ranked by project count. "
            "Example: activity_codes=['R21'], fiscal_years=[2018], group_by='organization' "
            "→ ranked list of institutions by R21 award count."
        ))] = None,
    ) -> SearchResult | GroupByResult:
        """Find NIH/HHS-funded research projects matching a topic and/or activity code.

        Use activity_codes for mechanism-specific queries (R01, T32, K-series, etc.).
        Use topic for research-subject text search. Both can be combined.
        Use group_by for 'which institution/state/IC got the most awards' questions —
        returns a ranked aggregation instead of individual project listings.
        For NIH-wide queries (all agencies, all mechanisms), you may omit topic and
        activity_codes if fiscal_years is provided — this enables questions like
        'largest single award in FY2024' without requiring a topic filter."""
        if not topic and not activity_codes and not fiscal_years:
            raise ValueError("Provide at least topic, activity_codes, or fiscal_years.")
        if topic:
            topic = validate_topic(topic)
        fiscal_years = validate_fiscal_years(fiscal_years)
        org_state = validate_state(org_state)

        criteria = build_criteria(topic=topic, fiscal_years=fiscal_years,
                                   org_state=org_state, agencies=agencies,
                                   activity_codes=activity_codes)

        # ── GROUP-BY path: paginate full cohort, aggregate ────────────
        if group_by:
            if group_by not in _GROUP_BY_FIELDS:
                raise ValueError(
                    f"Invalid group_by='{group_by}'. "
                    f"Must be one of: {', '.join(sorted(_GROUP_BY_FIELDS))}."
                )
            extractor = _GROUP_BY_FIELDS[group_by]
            base = {
                "criteria": criteria,
                "include_fields": AGG_FIELDS + ["ActivityCode"],
                "sort_field": "award_amount",
                "sort_order": "desc",
            }
            results, total, complete, pages, _ = await paginate_all(base)
            if active_only is not None:
                results = [r for r in results if r.get("is_active") == active_only]

            counts: Counter = Counter()
            dollars: defaultdict = defaultdict(float)
            for r in results:
                key = extractor(r)
                counts[key] += 1
                dollars[key] += r.get("award_amount") or 0

            buckets = [
                GroupByBucket(key=k, project_count=cnt, total_award_amount_usd=dollars[k])
                for k, cnt in counts.most_common(50)  # cap at 50 rows
            ]
            note = (
                f"Grouped {len(results):,} records by {group_by} "
                f"({len(counts):,} distinct values). "
                + ("Complete cohort retrieved." if complete
                   else f"Only {len(results):,} of {total:,} retrieved (10K ceiling). "
                        "Rankings may be approximate for large cohorts.")
            )
            return GroupByResult(
                group_by=group_by,
                total_matching_projects=total,
                buckets=buckets,
                cohort_complete=complete,
                note=note,
            )

        # ── Regular search path (individual projects) ─────────────────
        payload = {
            "criteria": criteria,
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
