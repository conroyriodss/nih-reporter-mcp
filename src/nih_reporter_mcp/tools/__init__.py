"""Tools submodule — one file per MCP tool.

Each tool module exposes a ``register(mcp)`` function; this file
aggregates them into ``register_tools(mcp)``.

To add a tool:
  1. Create ``tools/<name>.py`` with a ``register(mcp)`` function.
  2. Import it below and call ``<name>.register(mcp)`` inside register_tools.
"""

from __future__ import annotations

from nih_reporter_mcp.tools import (
    evidence_bundle,
    explain_health_topic,
    funding_trend,
    investigator,
    org_profile,
    overlap_check,
    project_by_id,
    publication_details,
    publications,
    recent_awards,
    search_projects,
    study_section_workload,
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
    overlap_check.register(mcp)
    study_section_workload.register(mcp)
    recent_awards.register(mcp)
    evidence_bundle.register(mcp)
    explain_health_topic.register(mcp)


__all__ = ["register_tools"]
