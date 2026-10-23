"""Thin entry point: creates FastMCP, wires tools, picks transport.

Run locally:          python -m nih_reporter_mcp.app
Databricks Apps:      the platform sets DATABRICKS_APP_PORT automatically.
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from nih_reporter_mcp.prompts import register_prompts
from nih_reporter_mcp.resources import register_resources
from nih_reporter_mcp.routes import register_routes
from nih_reporter_mcp.tools import register_tools

mcp = FastMCP(
    "NIH RePORTER",
    instructions=(
        "Query NIH and other HHS-agency research grant funding. Use "
        "search_funded_projects to locate specific awards; get_project_by_id "
        "for a direct lookup when you already have an ID; "
        "summarize_funding_by_topic for a reconciled total of recorded award "
        "amounts (exact only when the result reports complete=true and no "
        "excluded orphan subprojects; a free-text topic is a keyword cohort, "
        "while an official NIH RCDC spending_category name/ID uses RePORTER's "
        "live category tags, which can differ from NIH's published "
        "point-in-time RCDC tables); "
        "funding_trend_by_year to see how funding for a topic has changed over "
        "time; organization_funding_profile (exact name match by default) or "
        "investigator_portfolio to look up a specific institution or "
        "researcher; list_publications_for_project to find papers linked "
        "to a grant; and get_publication_details to resolve bare PubMed IDs "
        "into full citations (title, journal, authors, DOI) via NCBI "
        "E-utilities. Funding dollar amounts are available only for NIH, CDC, "
        "FDA, and ACF projects. No query can return more than 10,000 total "
        "matching records (an upstream limit); tools report this via a "
        "'complete' flag rather than silently truncating."
    ),
)

register_tools(mcp)
register_prompts(mcp)
register_resources(mcp)
register_routes(mcp)


def main() -> None:
    """Start the MCP server."""
    platform_port = os.environ.get("DATABRICKS_APP_PORT") or os.environ.get("PORT")
    if platform_port:
        mcp.run(transport="http", host="0.0.0.0", port=int(platform_port))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
