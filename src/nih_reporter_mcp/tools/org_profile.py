"""organization_funding_profile — funding profile for a named institution."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from datetime import datetime, timezone

from nih_reporter_mcp.config import MAX_RESULT_SET
from nih_reporter_mcp.models import COUNTING_UNIT_ALL, COUNTING_UNIT_WHOLE, OrgProfile, Provenance
from nih_reporter_mcp.utils import AGG_FIELDS, aggregate_funding, build_criteria, paginate_all, to_summary, validate_fiscal_years, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def organization_funding_profile(
        organization_name: Annotated[str, Field(description="Institution name, e.g. 'Johns Hopkins University'.")],
        fiscal_years: Annotated[list[int] | None, Field(description="Restrict to these fiscal years.")] = None,
        exact_match: Annotated[bool, Field(description="If true (default), exact name match to avoid combining similarly-named institutions.")] = True,
        funding_basis: Annotated[str, Field(description="'whole_award' (default) or 'all_records'.")] = "whole_award",
        include_provenance: Annotated[bool, Field(description="If true, attach a full Provenance audit trail.")] = False,
    ) -> OrgProfile:
        """Build a funding profile for a named institution."""
        organization_name = validate_topic(organization_name)
        fiscal_years = validate_fiscal_years(fiscal_years)

        criteria_kwargs: dict = {"fiscal_years": fiscal_years}
        if exact_match:
            criteria_kwargs["org_names_exact"] = [organization_name]
        else:
            criteria_kwargs["org_names"] = [organization_name]

        criteria = build_criteria(**criteria_kwargs)
        base_payload = {
            "criteria": criteria,
            "include_fields": AGG_FIELDS + ["ProjectTitle", "CoreProjectNum", "ApplId", "PrincipalInvestigators"],
            "sort_field": "award_amount",
            "sort_order": "desc",
        }
        if funding_basis not in ("whole_award", "all_records"):
            raise ValueError("funding_basis must be 'whole_award' or 'all_records'.")

        results, total, complete, pages_fetched, appl_ids = await paginate_all(base_payload)

        matched_orgs = sorted({(r.get("organization") or {}).get("org_name") for r in results if (r.get("organization") or {}).get("org_name")})
        agg = aggregate_funding(results, funding_basis=funding_basis)

        ic_counts: dict[str, int] = {}
        for r in results:
            ic = (r.get("agency_ic_admin") or {}).get("abbreviation")
            if ic:
                ic_counts[ic] = ic_counts.get(ic, 0) + 1
        top_ics = sorted(ic_counts, key=ic_counts.get, reverse=True)[:5]
        sample = [to_summary(r) for r in results[:5]]

        if total == 0 and exact_match:
            note = ("No projects found with that exact organization name. Retry with exact_match=false "
                    "to find the correct name, then re-run with the exact name from 'matched_org_names'.")
        elif complete:
            note = "Totals cover all matching projects."
            if not exact_match and len(matched_orgs) > 1:
                note += (f" Note: {len(matched_orgs)} distinct organization names matched "
                          f"({', '.join(matched_orgs[:5])}) -- totals combine all of them.")
        else:
            note = f"Hit the {MAX_RESULT_SET}-record safety cap; totals are a partial lower bound."

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
                source_record_ids=agg.contributing_ids[:500],
                id_conflicts=agg.id_conflicts,
            )

        return OrgProfile(
            organization_query=organization_name, matched_org_names=matched_orgs,
            fiscal_years=fiscal_years, total_matching_projects=total,
            projects_aggregated=agg.contributing_count, complete=complete,
            total_award_amount_usd=agg.total_award,
            funding_basis=funding_basis,
            records_with_missing_amount=agg.records_with_missing_amount,
            deduped_count=agg.deduped_count,
            subproject_excluded_count=agg.subproject_excluded_count,
            top_administering_ics=top_ics,
            sample_projects=sample, counting_unit=counting_unit,
            provenance=prov, note=note,
        )
