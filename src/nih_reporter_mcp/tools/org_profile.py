"""organization_funding_profile — funding profile for a named institution."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import MAX_RESULT_SET
from nih_reporter_mcp.models import OrgProfile
from nih_reporter_mcp.utils import AGG_FIELDS, build_criteria, paginate_all, to_summary, validate_fiscal_years, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def organization_funding_profile(
        organization_name: Annotated[str, Field(description="Institution name, e.g. 'Johns Hopkins University'.")],
        fiscal_years: Annotated[list[int] | None, Field(description="Restrict to these fiscal years.")] = None,
        exact_match: Annotated[bool, Field(description="If true (default), exact name match to avoid combining similarly-named institutions.")] = True,
    ) -> OrgProfile:
        """Build a funding profile for a named institution."""
        organization_name = validate_topic(organization_name)
        fiscal_years = validate_fiscal_years(fiscal_years)

        criteria_kwargs: dict = {"fiscal_years": fiscal_years}
        if exact_match:
            criteria_kwargs["org_names_exact"] = [organization_name]
        else:
            criteria_kwargs["org_names"] = [organization_name]

        base_payload = {
            "criteria": build_criteria(**criteria_kwargs),
            "include_fields": AGG_FIELDS + ["ProjectTitle", "CoreProjectNum", "ApplId", "PrincipalInvestigators"],
            "sort_field": "award_amount",
            "sort_order": "desc",
        }
        results, total, complete = await paginate_all(base_payload)

        matched_orgs = sorted({(r.get("organization") or {}).get("org_name") for r in results if (r.get("organization") or {}).get("org_name")})
        total_award = sum(r.get("award_amount") or 0 for r in results)

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

        return OrgProfile(
            organization_query=organization_name, matched_org_names=matched_orgs,
            fiscal_years=fiscal_years, total_matching_projects=total,
            projects_aggregated=len(results), complete=complete,
            total_award_amount_usd=round(total_award, 2), top_administering_ics=top_ics,
            sample_projects=sample, note=note,
        )
