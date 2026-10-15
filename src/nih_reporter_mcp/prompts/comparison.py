"""Prompt: compare official RCDC spending category vs free-text search."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="compare_rcdc_vs_freetext",
        description=(
            "Compare NIH's official RCDC spending category total against a "
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
            f"   fiscal_years=[{fiscal_year}] to get the official RCDC total.\n"
            f"2. Call summarize_funding_by_topic with "
            f"   topic=\"{topic}\" and "
            f"   fiscal_years=[{fiscal_year}] to get the free-text total.\n\n"
            f"Present both dollar amounts side by side and explain why they "
            f"differ. The RCDC number is a congressionally-mandated "
            f"categorisation maintained by NIH staff; the free-text number "
            f"is keyword matching across project abstracts and terms. "
            f"Neither is \"wrong\" -- they answer different questions."
        )
