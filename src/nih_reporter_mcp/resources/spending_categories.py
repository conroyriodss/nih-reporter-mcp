"""Resource: browsable list of built-in RCDC spending categories."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from nih_reporter_mcp.config import SPENDING_CATEGORIES


def register(mcp: FastMCP) -> None:
    @mcp.resource(
        "nih-reporter://spending-categories",
        name="spending_categories",
        description=(
            "Curated lookup table of NIH RCDC spending category names and "
            "their numeric IDs. Use these names or IDs with the "
            "spending_category parameter on summarize_funding_by_topic and "
            "funding_trend_by_year for official, congressionally-mandated "
            "funding totals."
        ),
    )
    def spending_categories() -> str:
        rows = [
            {"name": name, "category_id": cid}
            for name, cid in sorted(SPENDING_CATEGORIES.items())
        ]
        return json.dumps(
            {"count": len(rows), "categories": rows},
            indent=2,
        )
