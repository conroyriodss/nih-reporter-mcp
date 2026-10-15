"""Prompt: competitive research landscape summary for a topic."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="research_landscape_summary",
        description=(
            "Produce a competitive landscape summary for a research area: "
            "total NIH investment, multi-year trend, and the most prominent "
            "funded groups. Composes three existing tools into a single "
            "analyst workflow."
        ),
    )
    def research_landscape_summary(
        topic: str, years_back: str = "5"
    ) -> str:
        yb = int(years_back)
        current_fy = 2026
        start_fy = current_fy - yb + 1
        fy_list = list(range(start_fy, current_fy + 1))
        fy_str = ", ".join(str(y) for y in fy_list)

        return (
            f"Produce a competitive research landscape summary for "
            f'"{topic}" covering FY{start_fy}–FY{current_fy} '
            f"({yb} years). Follow these steps:\n\n"
            f"1. Call **summarize_funding_by_topic** with "
            f'   topic="{topic}" and fiscal_years=[{fy_str}] to get the '
            f"   exact total NIH/HHS investment and project count for the "
            f"   full period.\n"
            f"2. Call **funding_trend_by_year** with "
            f'   topic="{topic}", start_year={start_fy}, '
            f"   end_year={current_fy} to show the year-over-year funding "
            f"   trajectory.\n"
            f"3. Call **search_funded_projects** with "
            f'   topic="{topic}", fiscal_years=[{current_fy}], '
            f"   sort_by_award=true, limit=10 to identify the largest "
            f"   currently-funded efforts and their institutions.\n\n"
            f"Synthesize the results into a landscape summary covering:\n"
            f"- **Total investment**: exact dollar figure over the period, "
            f"  noting whether it covers all matching projects (complete "
            f"  flag) or hit the 10,000-record retrieval cap.\n"
            f"- **Trend direction**: growing, shrinking, or flat, with "
            f"  year-over-year figures.\n"
            f"- **Top 3–5 funded groups/institutions**: the most prominent "
            f"  organisations and PIs working in this area based on award "
            f"  size.\n"
            f"- **Scope disclaimer**: explicitly note that this reflects "
            f"  NIH/HHS funding only — the full research landscape may "
            f"  include non-NIH-funded work (other federal agencies, "
            f"  industry R&D, international efforts, philanthropic "
            f"  funding) that is outside RePORTER's scope."
        )
