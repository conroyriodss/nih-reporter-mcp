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
    APPLICATION_TYPES,
    parse_application_type,
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

# Multi-valued group_by dimensions (return a LIST of keys per record):
_GROUP_BY_MULTI = {"principal_investigator"}


def _extract_pis(r: dict) -> list[str]:
    """Extract PI names from a record. Each listed PI is credited once per award."""
    pis = r.get("principal_investigators") or []
    return [p.get("full_name") or "Unknown" for p in pis if p.get("full_name")]


_GROUP_BY_FIELDS = {
    "organization": lambda r: (r.get("organization") or {}).get("org_name") or "Unknown",
    "activity_code": lambda r: r.get("activity_code") or "Unknown",
    "org_state": lambda r: (r.get("organization") or {}).get("org_state") or "Unknown",
    "administering_ic": lambda r: (r.get("agency_ic_admin") or {}).get("abbreviation") or "Unknown",
    "application_type": lambda r: APPLICATION_TYPES.get(parse_application_type(r.get("project_num")), "Unknown"),
    "principal_investigator": _extract_pis,  # multi-valued: returns list
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
        application_types: Annotated[list[int] | None, Field(description=(
            "Filter by application type code (leading digit of the NIH project number). "
            "1=New, 2=Competing Renewal, 3=Supplement, 4=Extension, "
            "5=Non-Competing Continuation, 6=Change of Grantee, 7=Application, "
            "8=Merit Extension, 9=Other. "
            "Use this for lifecycle questions like 'non-competing continuations' or 'new awards only'. "
            "Filtered SERVER-SIDE (exact counts, no 10K ceiling). Example: application_types=[5] for non-competing continuations."
        ))] = None,
        group_by: Annotated[str | None, Field(description=(
            "Instead of listing individual projects, GROUP results by this dimension "
            "and return a RANKED table of (key, project_count, total_award). "
            "Use this for 'which institution/state/IC got the most' questions. "
            "Valid values: 'organization', 'activity_code', 'org_state', 'administering_ic', 'application_type', 'principal_investigator'. "
            "When group_by='application_type', counts are EXACT (server-side faceting). "
            "For other dimensions, grouping uses up to 10,000 records — honest truncation "
            "flags are included when the cohort exceeds this ceiling. "
            "The result includes total_matching_projects so you can compute percentages. "
            "A single group_by call IS the complete answer — no per-IC verification needed. "
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
        'largest single award in FY2024' without requiring a topic filter.

        IMPORTANT — keyword search vs program membership:
        topic= searches ALL text fields (title, abstract, terms). For named NIH programs
        (HuBMAP, SPARC, All of Us, etc.), keyword search is an APPROXIMATION — it finds
        projects that mention the program, not a program roster. RePORTER does not expose
        a Common Fund or program-membership filter. When answering 'how many awards in
        program X', state the keyword-based nature in the headline, not a footnote.

        Response structure for count/total questions:
        Lead with ONE number + its basis in the first sentence. Offer parent-vs-total or
        keyword-vs-RCDC alternatives as labeled follow-ups. Never present competing
        numbers without stating which question each answers.

        IMPORTANT — records vs awards for center grants:
        Center grants (P-series P30/P41/P50, U-series U54, etc.) fan out into many
        subproject records per award. A raw record count massively overcounts awards.
        group_by='application_type' already returns DEDUPLICATED award counts
        (exclude_subprojects=True). For non-group_by queries, total_matching_projects
        is a RECORD count. When answering 'how many awards/renewals', use the deduped
        count as the headline. If only a record count is available, say so explicitly:
        'N records (not deduplicated; center grants span multiple records per award)'
        and do NOT compute percentage changes from inflated record counts."""
        if not topic and not activity_codes and not fiscal_years:
            raise ValueError("Provide at least topic, activity_codes, or fiscal_years.")
        if topic:
            topic = validate_topic(topic)
        fiscal_years = validate_fiscal_years(fiscal_years)
        org_state = validate_state(org_state)

        criteria = build_criteria(
            topic=topic, fiscal_years=fiscal_years,
            org_state=org_state, agencies=agencies,
            activity_codes=activity_codes,
            award_types=application_types,
        )

        # ── GROUP-BY path ──────────────────────────────────────────────
        if group_by:
            if group_by not in _GROUP_BY_FIELDS:
                raise ValueError(
                    f"Invalid group_by='{group_by}'. "
                    f"Must be one of: {', '.join(sorted(_GROUP_BY_FIELDS))}."
                )

            # ── Server-side faceting for application_type ─────────────
            # RePORTER lacks native facets, but we can synthesize exact
            # counts by issuing one count-only query per award_type code.
            # This avoids the 10K pagination ceiling entirely.
            #
            # IMPORTANT: counts use exclude_subprojects=True so that each
            # core project is counted ONCE (award count, not record count).
            # Without this, center grants (P30/P41/P50/U54) inflate by
            # 5-100x because each subproject is a separate record.
            if group_by == "application_type":
                from nih_reporter_mcp.utils import APPLICATION_TYPES
                import asyncio as _aio

                # Get baseline total (deduplicated: awards, not records)
                _dedup_criteria = {**criteria, "exclude_subprojects": True}
                _base_data = await post_json(
                    PROJECTS_SEARCH, {"criteria": _dedup_criteria, "offset": 0, "limit": 1}
                )
                total = (_base_data.get("meta") or {}).get("total", 0)

                # Parallel count queries for each award type (deduplicated)
                async def _count_type(code: int) -> tuple[int, str, int]:
                    c2 = {**criteria, "award_types": [str(code)],
                          "exclude_subprojects": True}
                    d = await post_json(
                        PROJECTS_SEARCH, {"criteria": c2, "offset": 0, "limit": 1}
                    )
                    return code, APPLICATION_TYPES.get(code, f"Type {code}"), (d.get("meta") or {}).get("total", 0)

                type_results = await _aio.gather(
                    *[_count_type(c) for c in sorted(APPLICATION_TYPES)]
                )
                buckets = [
                    GroupByBucket(
                        key=label,
                        project_count=cnt,
                        total_award_amount_usd=0,  # not available without fetching records
                    )
                    for _code, label, cnt in sorted(type_results, key=lambda x: -x[2])
                    if cnt > 0
                ]
                group_sum = sum(b.project_count for b in buckets)
                # Remainder bucket: catch any codes not in APPLICATION_TYPES
                remainder = total - group_sum
                if remainder > 0:
                    buckets.append(GroupByBucket(
                        key="Unclassified / other codes",
                        project_count=remainder,
                        total_award_amount_usd=0,
                    ))
                    group_sum = total  # parts now sum to whole
                note = (
                    f"Deduplicated award counts by application type "
                    f"(subproject records excluded — each core project counted once). "
                    f"Total matching awards: {total:,}. Sum of types: {group_sum:,}. "
                    f"These are COMPLETE counts, not limited by the 10K retrieval ceiling. "
                    f"Dollar amounts are not available in this mode — use application_types "
                    f"filter for dollar totals on a specific type."
                )
                return GroupByResult(
                    group_by=group_by,
                    total_matching_projects=total,
                    buckets=buckets,
                    cohort_complete=True,
                    note=note,
                )

            # ── Client-side grouping for other dimensions ─────────────
            extractor = _GROUP_BY_FIELDS[group_by]
            is_multi = group_by in _GROUP_BY_MULTI
            base = {
                "criteria": criteria,
                "include_fields": AGG_FIELDS + ["ActivityCode", "ProjectNum"]
                    + (["PrincipalInvestigators"] if group_by == "principal_investigator" else []),
                "sort_field": "award_amount",
                "sort_order": "desc",
            }
            results, total, complete, pages, _ = await paginate_all(base)
            if active_only is not None:
                results = [r for r in results if r.get("is_active") == active_only]
            counts: Counter = Counter()
            dollars: defaultdict = defaultdict(float)
            for r in results:
                amt = r.get("award_amount") or 0
                if is_multi:
                    # Multi-valued: each key credited once per award
                    keys = extractor(r)
                    for key in keys:
                        counts[key] += 1
                        dollars[key] += amt
                else:
                    key = extractor(r)
                    counts[key] += 1
                    dollars[key] += amt

            buckets = [
                GroupByBucket(key=k, project_count=cnt, total_award_amount_usd=dollars[k])
                for k, cnt in counts.most_common(50)  # cap at 50 rows
            ]
            pi_note = (
                " Multi-PI awards credit each listed PI once, so award-count "
                "and dollar sums will exceed the project total."
            ) if group_by == "principal_investigator" else ""
            if complete:
                note = (
                    f"Grouped {len(results):,} records by {group_by} "
                    f"({len(counts):,} distinct values). Complete cohort retrieved."
                    + pi_note
                )
            else:
                note = (
                    f"Based on top {len(results):,} of {total:,} records (by award amount). "
                    f"Counts are LOWER BOUNDS — the full cohort exceeds the 10K retrieval ceiling. "
                    f"Percentages are approximate. Rankings among top groups are reliable "
                    f"but small groups may be undercounted."
                    + pi_note
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
            results = [r for r in results if r.get("is_active") == active_only]
        projects = [to_summary(r) for r in results[:limit]]
        return SearchResult(
            total_matching_projects=total, returned=len(projects),
            truncated=total > len(projects), projects=projects,
        )
