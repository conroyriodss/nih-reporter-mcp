"""Prompts submodule — reusable prompt templates.

Each prompt module exposes a ``register(mcp)`` function.
"""

from __future__ import annotations

from nih_reporter_mcp.prompts import comparison, funding_analysis


def register_prompts(mcp) -> None:
    """Register all prompts with the MCP server."""
    funding_analysis.register(mcp)
    comparison.register(mcp)


__all__ = ["register_prompts"]
