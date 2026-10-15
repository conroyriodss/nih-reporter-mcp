"""Tools submodule — one file per MCP tool.

Each tool module exposes a ``register(mcp)`` function; this file
aggregates them into ``register_tools(mcp)``.

To add a tool:
  1. Create ``tools/<name>.py`` with a ``register(mcp)`` function.
  2. Import it below and call ``<name>.register(mcp)`` inside register_tools.
"""

from __future__ import annotations

from nih_reporter_mcp.tools import (
    funding_trend,
    investigator,
    org_profile,
    project_by_id,
    publication_details,
    publications,
    search_projects,
    summarize_funding,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    search_projects.register(mcp)
    summarize_funding.register(mcp)
    funding_trend.register(mcp)
    org_profile.register(mcp)
    project_by_id.register(mcp)
    investigator.register(mcp)
    publications.register(mcp)
    publication_details.register(mcp)


__all__ = ["register_tools"]
