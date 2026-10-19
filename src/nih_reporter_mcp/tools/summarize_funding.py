"""summarize_funding_by_topic — exact total investment via full pagination."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from typing import Literal

from nih_reporter_mcp.config import MAX_RESULT_SET, resolve_spending_category
from nih_reporter_mcp.models import COUNTING_UNIT_ALL, COUNTING_UNIT_WHOLE, FundingSummary, Provenance
from nih_reporter_mcp.utils import AGG_FIELDS, MAX_PROVENANCE_IDS, aggregate_funding, build_criteria, paginate_all, validate_fiscal_years, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def summarize_funding_by_topic(
        topic: Annotated[str | None, Field(description="Research topic or keywords to total funding for. Omit if using spending_category instead.")] = None,
        fiscal_years: Annotated[list[int] | None, Field(description="Fiscal years to include, e.g. [2022, 2023, 2024].")] = None,
        agencies: Annotated[list[str] | None, Field(description="Limit to agency/IC abbreviations, e.g. ['NCI'].")] = None,
        activity_codes: Annotated[list[str] | None, Field(description=(
            "NIH activity codes to filter by, e.g. ['R01']. Use for mechanism-specific "
            "funding questions. Do NOT put activity codes in topic — use this parameter instead."
        ))] = None,
        application_types: Annotated[list[int] | None, Field(description=(
            "Filter by application type code: 1=New, 2=Competing Renewal, "
            "3=Supplement, 4=Extension, 5=Non-Competing Continuation, "
            "6=Change of Grantee, 7=Application, 8=Merit Extension, 9=Other. "
            "Server-side filter."
        ))] = None,
        spending_category: Annotated[str | int | None, Field(description="NIH RCDC spending category -- name (e.g. 'Alzheimer's Disease', 'Cancer', 'Long COVID') or numeric ID. Aggregates live RePORTER data tagged with this category; note this may differ from NIH's frozen published RCDC totals, which are point-in-time snapshots.")] = None,
        active_only: Annotated[bool | None, Field(description="If true, active projects only (client-side filtered). If false, inactive only. Omit for all.")] = None,
        funding_basis: Annotated[str, Field(description="'whole_award' (default, excludes subproject records to avoid double-counting) or 'all_records' (legacy, sums every record including subprojects).")] = "whole_award",
        include_provenance: Annotated[bool, Field(description="If true, attach a full Provenance audit trail (heavier payload).")] = False,
    ) -> FundingSummary:
        """Quantify total NIH/HHS investment in a research topic (oversight view).
        Paginates through ALL matching projects (up to 10,000) for an exact total."""
        if not topic and not spending_category and not activity_codes and not fiscal_years:
            raise ValueError("Provide at least one of topic, spending_category, activity_codes, or fiscal_years.")
        if topic:
            topic = validate_topic(topic)
        fiscal_years = validate_fiscal_years(fiscal_years)
        category_id = resolve_spending_category(spending_category) if spending_category else None

        criteria = build_criteria(
            topic=topic, fiscal_years=fiscal_years, agencies=agencies,
            spending_categories=[category_id] if category_id else None,
            activity_codes=activity_codes,
            award_types=application_types,
        )
        if funding_basis not in ("whole_award", "all_records"):
            raise ValueError("funding_basis must be 'whole_award' or 'all_records'.")

        base_payload = {
            "criteria": criteria,
            "include_fields": AGG_FIELDS
                + (["IsActive"] if active_only is not None else []),
            "sort_field": "award_amount",
            "sort_order": "desc",
        }
        results, total, complete, pages_fetched, appl_ids = await paginate_all(base_payload)

        if active_only is not None:
            results = [r for r in results if r.get("is_active") == active_only]

        agg = aggregate_funding(results, funding_basis=funding_basis)
        orgs = {(r.get("organization") or {}).get("org_name") for r in results if (r.get("organization") or {}).get("org_name")}
        ics = {(r.get("agency_ic_admin") or {}).get("abbreviation") for r in results if (r.get("agency_ic_admin") or {}).get("abbreviation")}

        exact = complete and agg.is_exact
        note_parts = []
        if exact:
            note_parts.append("Total is exact: every matching project was aggregated, none had missing amounts or unresolved conflicts.")
        if not complete:
            note_parts.append(f"Only the top {len(results)} of {total} matching projects were aggregated "
                    f"(hit RePORTER's {MAX_RESULT_SET}-record retrieval ceiling). Narrow the query for a complete figure.")
        if agg.has_unresolved_conflicts:
            note_parts.append(f"{len(agg.id_conflicts)} application ID(s) appeared with conflicting amounts across pages; "
                    "first occurrence was counted. Enable provenance to inspect conflicts.")
        if agg.orphan_children:
            note_parts.append(f"{len(agg.orphan_children)} excluded subproject(s) had no corresponding parent record in the "
                    "retrieved cohort; their associated award-family investment may not be reflected in this total.")
        note = " ".join(note_parts) if note_parts else ""
        if agg.records_with_missing_amount > 0:
            note += (f" {agg.records_with_missing_amount} record(s) had no funding amount on "
                     "file and are excluded from the total (not counted as $0).")
        if active_only is None:
            note += " Includes both active and expired/inactive projects across all time."
        else:
            note += f" Filtered client-side to active_only={active_only}; total_matching_projects is the unfiltered count."

        counting_unit = COUNTING_UNIT_WHOLE if funding_basis == "whole_award" else COUNTING_UNIT_ALL

        prov = None
        if include_provenance:
            prov = Provenance(
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                query_criteria=criteria,
                total_matching=total,
                records_aggregated=agg.contributing_count,
                complete=complete,
                pages_fetched=pages_fetched,
                deduped_count=agg.deduped_count,
                subproject_excluded_count=agg.subproject_excluded_count,
                records_with_missing_amount=agg.records_with_missing_amount,
                funding_basis=funding_basis,
                source_record_ids=agg.contributing_ids[:MAX_PROVENANCE_IDS],
                id_conflicts=agg.id_conflicts,
            )

        return FundingSummary(
            topic=topic or (f"spending_category:{spending_category}" if spending_category else (f"activity_codes:{activity_codes}" if activity_codes else f"all_nih_fy:{fiscal_years}")),
            fiscal_years=fiscal_years, total_matching_projects=total,
            projects_aggregated=agg.contributing_count,
            complete=complete, total_award_amount_usd=agg.total_award,
            funding_basis=funding_basis,
            records_with_missing_amount=agg.records_with_missing_amount,
            deduped_count=agg.deduped_count,
            subproject_excluded_count=agg.subproject_excluded_count,
            distinct_organizations=len(orgs), distinct_administering_ics=len(ics),
            pages_fetched=pages_fetched, counting_unit=counting_unit,
            provenance=prov, note=note,
        )
