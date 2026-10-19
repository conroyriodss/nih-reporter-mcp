"""Resources submodule — static and dynamic data exposed to MCP clients.

Each resource module exposes a ``register(mcp)`` function.
"""

from __future__ import annotations

from nih_reporter_mcp.resources import server_info, spending_categories


def register_resources(mcp) -> None:
    """Register all resources with the MCP server."""
    spending_categories.register(mcp)
    server_info.register(mcp)
    response_guidelines.register(mcp)


__all__ = ["register_resources"]
