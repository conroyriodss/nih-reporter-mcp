"""Prompt: structured funding overview for a research topic."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="funding_overview",
        description=(
            "Generate a structured funding overview for a research topic. "
            "Guides the model to call the right tools and produce a "
            "standardised report with total investment, top institutions, "
            "year-over-year trend, and key projects."
        ),
    )
    def funding_overview(topic: str, fiscal_year: str = "2024") -> str:
        return (
            f"Produce a structured NIH funding overview for \"{topic}\" "
            f"in FY{fiscal_year}. Follow these steps:\n\n"
            f"1. Use summarize_funding_by_topic to get the total "
            f"   investment (state whether the result is complete) and project count for \"{topic}\" in "
            f"   fiscal_years=[{fiscal_year}].\n"
            f"2. Use search_funded_projects to find the 10 largest awards "
            f"   for the same topic and year (sort_by_award=true, limit=10).\n"
            f"3. Use funding_trend_by_year to show the 5-year trend "
            f"   (start_year={int(fiscal_year)-4}, end_year={fiscal_year}).\n\n"
            f"Present the results as:\n"
            f"- **Total investment**: exact dollar figure, noting whether it "
            f"  covers all matching projects (complete flag).\n"
            f"- **5-year trend table**: fiscal year, project count, total $.\n"
            f"- **Top 10 awards table**: project number, title, PI(s), "
            f"  organization, award amount.\n"
            f"- **Notable observations**: any patterns in ICs, institutions, "
            f"  or funding trajectory."
        )

    @mcp.prompt(
        name="institution_report",
        description=(
            "Generate a comprehensive funding report for a specific "
            "institution, including total funding, top ICs, and sample "
            "projects."
        ),
    )
    def institution_report(organization: str, fiscal_year: str = "2024") -> str:
        return (
            f"Build a comprehensive NIH funding report for "
            f"\"{organization}\" in FY{fiscal_year}.\n\n"
            f"1. Use organization_funding_profile with exact_match=true and "
            f"   fiscal_years=[{fiscal_year}].\n"
            f"2. If no results, retry with exact_match=false to find the "
            f"   correct institutional name, then re-run with the exact name.\n\n"
            f"Present:\n"
            f"- Total award amount and project count\n"
            f"- Top administering ICs (with counts)\n"
            f"- 5 largest awards with project numbers, titles, and PIs\n"
            f"- Whether the totals are complete or hit the 10K ceiling"
        )
