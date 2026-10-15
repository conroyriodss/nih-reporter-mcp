"""Prompts submodule — reusable prompt templates.

Each prompt module exposes a ``register(mcp)`` function.

Current prompt count: 9
  funding_analysis   -> funding_overview, institution_report          (2)
  comparison         -> compare_rcdc_vs_freetext                     (1)
  landscape          -> research_landscape_summary                   (1)
  program_officer    -> portfolio_brief, other_support_review,
                        investment_to_outputs                         (3)
  citizen_scientist  -> explain_funding_landscape, follow_the_evidence (2)
"""

from __future__ import annotations

from nih_reporter_mcp.prompts import (
    citizen_scientist,
    comparison,
    funding_analysis,
    landscape,
    program_officer,
)


def register_prompts(mcp) -> None:
    """Register all prompts with the MCP server."""
    funding_analysis.register(mcp)
    comparison.register(mcp)
    landscape.register(mcp)
    program_officer.register(mcp)
    citizen_scientist.register(mcp)


__all__ = ["register_prompts"]
