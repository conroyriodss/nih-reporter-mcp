"""export_evidence_bundle — inspectable audit trail for any funding claim."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from nih_reporter_mcp.config import MAX_RESULT_SET, resolve_spending_category
from nih_reporter_mcp.models import COUNTING_UNIT_ALL, COUNTING_UNIT_WHOLE, FundingSummary, Provenance
from nih_reporter_mcp.utils import (
    validate_string_length,
    AGG_FIELDS,
    MAX_PROVENANCE_IDS,
    aggregate_funding,
    build_criteria,
    paginate_all,
    validate_fiscal_years,
    validate_topic,
)


class EvidenceBundle(BaseModel):
    label: str | None
    summary: FundingSummary
    provenance: Provenance
    reproduction_note: str = Field(
        ...,
        description="How to independently reproduce this figure from the source records.",
    )


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def export_evidence_bundle(
        topic: Annotated[
            str | None,
            Field(description="Research topic or keywords. Omit if using spending_category."),
        ] = None,
        spending_category: Annotated[
            str | int | None,
            Field(description="NIH official RCDC spending category — name or numeric ID."),
        ] = None,
        fiscal_years: Annotated[
            list[int] | None,
            Field(description="Fiscal years to include."),
        ] = None,
        agencies: Annotated[
            list[str] | None,
            Field(description="Limit to agency/IC abbreviations."),
        ] = None,
        label: Annotated[
            str | None,
            Field(description="Optional human-readable label for this bundle."),
        ] = None,
        funding_basis: Annotated[
            str,
            Field(description="'whole_award' (default) or 'all_records'."),
        ] = "whole_award",
    ) -> EvidenceBundle:
        """Produce an inspectable evidence bundle for a funding claim.

        Runs the same aggregation as summarize_funding_by_topic but always
        includes full provenance (query criteria, source record IDs, timing)
        and a reproduction note. Use this when the audience needs to verify
        or audit a specific dollar figure.
        """
        if not topic and not spending_category:
            raise ValueError("Provide at least one of topic or spending_category.")
        if topic:
            topic = validate_topic(topic)
        if label:
            label = validate_string_length(label, "label")
        fiscal_years = validate_fiscal_years(fiscal_years)
        category_id = (
            resolve_spending_category(spending_category) if spending_category else None
        )

        criteria = build_criteria(
            topic=topic,
            fiscal_years=fiscal_years,
            agencies=agencies,
            spending_categories=[category_id] if category_id else None,
        )
        if funding_basis not in ("whole_award", "all_records"):
            raise ValueError("funding_basis must be 'whole_award' or 'all_records'.")

        base_payload = {
            "criteria": criteria,
            "include_fields": AGG_FIELDS,
            "sort_field": "award_amount",
            "sort_order": "desc",
        }
        results, total, complete, pages_fetched, appl_ids = await paginate_all(
            base_payload
        )

        agg = aggregate_funding(results, funding_basis=funding_basis)
        orgs = {
            (r.get("organization") or {}).get("org_name")
            for r in results
            if (r.get("organization") or {}).get("org_name")
        }
        ics = {
            (r.get("agency_ic_admin") or {}).get("abbreviation")
            for r in results
            if (r.get("agency_ic_admin") or {}).get("abbreviation")
        }

        exact = complete and agg.records_with_missing_amount == 0
        note = (
            "Total is exact: every matching project was aggregated, none had missing amounts."
            if exact
            else (
                f"Only the top {len(results)} of {total} matching projects "
                f"were aggregated (hit RePORTER's {MAX_RESULT_SET}-record "
                "retrieval ceiling). Narrow the query for an exact figure."
            )
        )
        if agg.records_with_missing_amount > 0:
            note += (f" {agg.records_with_missing_amount} record(s) had no funding amount "
                     "on file and are excluded from the total (not counted as $0).")

        counting_unit = COUNTING_UNIT_WHOLE if funding_basis == "whole_award" else COUNTING_UNIT_ALL

        # Use contributing IDs (post-exclusion) for provenance —
        # only appl_ids that actually contributed to the dollar total.
        source_ids = agg.contributing_ids[:MAX_PROVENANCE_IDS]

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
            source_record_ids=source_ids,
            id_conflicts=agg.id_conflicts,
        )

        summary = FundingSummary(
            topic=topic or f"spending_category:{spending_category}",
            fiscal_years=fiscal_years,
            total_matching_projects=total,
            projects_aggregated=agg.contributing_count,
            complete=complete,
            total_award_amount_usd=agg.total_award,
            funding_basis=funding_basis,
            records_with_missing_amount=agg.records_with_missing_amount,
            deduped_count=agg.deduped_count,
            subproject_excluded_count=agg.subproject_excluded_count,
            distinct_organizations=len(orgs),
            distinct_administering_ics=len(ics),
            pages_fetched=pages_fetched,
            counting_unit=counting_unit,
            provenance=prov,
            note=note,
        )

        # Build reproduction note describing the ACTUAL algorithm.
        cap_note = ""
        total_contributing = len(agg.contributing_ids)
        if total_contributing > MAX_PROVENANCE_IDS:
            cap_note = (
                f" source_record_ids lists {len(source_ids)} of the "
                f"{total_contributing} contributing appl_ids (capped at "
                f"{MAX_PROVENANCE_IDS} for payload size); "
                "records_aggregated gives the true contributing count."
            )

        if funding_basis == "whole_award":
            repro = (
                "To reproduce: (1) POST query_criteria to source_api and "
                "paginate all pages (offset in steps of 500 up to the "
                "record retrieval cap). (2) Exclude any record whose "
                "subproject_id is non-null. (3) Deduplicate by appl_id. "
                "(4) Exclude records whose award_amount is null (these are "
                "reported separately in records_with_missing_amount, not "
                "counted as $0). (5) Sum award_amount over the remaining "
                "records. The contributing appl_ids are listed in "
                "source_record_ids; records_aggregated gives the true "
                "contributing count."
                + cap_note
            )
        else:
            repro = (
                "To reproduce: (1) POST query_criteria to source_api and "
                "paginate all pages (offset in steps of 500 up to the "
                "record retrieval cap). (2) Deduplicate by appl_id. "
                "(3) Exclude records whose award_amount is null (these are "
                "reported separately in records_with_missing_amount, not "
                "counted as $0). (4) Sum award_amount over all remaining "
                "records (including subprojects). The contributing appl_ids "
                "are listed in source_record_ids; records_aggregated gives "
                "the true contributing count."
                + cap_note
            )

        return EvidenceBundle(
            label=label,
            summary=summary,
            provenance=prov,
            reproduction_note=repro,
        )
