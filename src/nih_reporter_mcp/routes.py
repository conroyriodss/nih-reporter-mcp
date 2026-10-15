"""Custom HTTP routes: /health and /version.

These sit alongside the MCP transport endpoint and are useful for
load-balancer probes, deployment smoke tests, and quick diagnostics.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from nih_reporter_mcp import __version__
from nih_reporter_mcp.config import API_BASE, SPENDING_CATEGORIES


def register_routes(mcp: FastMCP) -> None:
    """Register custom HTTP routes on the MCP server."""

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        """Liveness / readiness probe.

        Returns 200 with a JSON body summarising the server's capabilities.
        Suitable for Databricks Apps health checks, cloud.gov probes, or
        any HTTP load balancer.
        """
        return JSONResponse(
            {
                "status": "ok",
                "server": "nih-reporter-mcp",
                "version": __version__,
                "upstream_api": API_BASE,
            }
        )

    @mcp.custom_route("/version", methods=["GET"])
    async def version(request: Request) -> Response:
        """Detailed version and capability report."""
        return JSONResponse(
            {
                "server": "nih-reporter-mcp",
                "version": __version__,
                "tools": 8,
                "prompts": 3,
                "resources": 2,
                "spending_categories": len(SPENDING_CATEGORIES),
                "upstream_api": API_BASE,
            }
        )
