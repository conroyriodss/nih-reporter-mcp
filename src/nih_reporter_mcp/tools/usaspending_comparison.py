"""STUB: not yet implemented.

Planned: query USAspending.gov API to compare NIH's investment in a topic
against total federal spending across all agencies, for a cross-agency
oversight view that RePORTER alone cannot provide.

This file is an intentional placeholder — it documents a roadmap item
without exposing a broken tool to MCP clients.  It is deliberately NOT
registered in tools/__init__.py.

See docs/roadmap.md for the full Tier 2 feature plan.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:  # noqa: ARG001
    """Register USAspending comparison tool.

    TODO: Implement USAspending.gov API integration.
    - Endpoint: https://api.usaspending.gov/api/v2/search/spending_by_award/
    - Compare NIH's topic-specific funding against government-wide spending.
    - Support CFDA program and agency filters.
    - Return side-by-side totals: NIH (from RePORTER) vs all-agency (from
      USAspending), with links to both sources.
    - Rate limit: polite 1 req/sec, same as RePORTER.
    """
    raise NotImplementedError(
        "usaspending_comparison is a Tier 2 roadmap item. "
        "See docs/roadmap.md for planned implementation."
    )
