"""Prompt: compare official RCDC spending category vs free-text search."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="compare_rcdc_vs_freetext",
        description=(
            "Compare a live RCDC spending-category aggregation against a "
            "free-text keyword search for the same topic. Surfaces the "
            "well-documented divergence between curated categorisation and "
            "naive text matching."
        ),
    )
    def compare_rcdc_vs_freetext(
        topic: str, fiscal_year: str = "2023"
    ) -> str:
        return (
            f"Compare two ways of measuring NIH investment in "
            f"\"{topic}\" for FY{fiscal_year}:\n\n"
            f"1. Call summarize_funding_by_topic with "
            f"   spending_category=\"{topic}\" and "
            f"   fiscal_years=[{fiscal_year}] to get the live RCDC-category "
            f"   aggregation (note: this aggregates current RePORTER data "
            f"   tagged with this category, which may differ from NIH's "
            f"   frozen published RCDC annual totals).\n"
            f"2. Call summarize_funding_by_topic with "
            f"   topic=\"{topic}\" and "
            f"   fiscal_years=[{fiscal_year}] to get the free-text total.\n\n"
            f"Present both dollar amounts side by side and explain why they "
            f"differ. The RCDC number aggregates projects currently tagged "
            f"with a congressionally-mandated category in RePORTER (which "
            f"updates continuously and may not match NIH's frozen published "
            f"annual totals); the free-text number is keyword matching "
            f"across project abstracts and terms. RCDC categories can also "
            f"overlap, so summing across categories double-counts. Neither "
            f"method is \"wrong\" -- they answer different questions."
        )
