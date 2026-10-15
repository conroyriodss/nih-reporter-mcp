"""Resource: server metadata and upstream API constraints."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from nih_reporter_mcp import __version__
from nih_reporter_mcp.config import (
    API_BASE,
    EARLIEST_FISCAL_YEAR,
    LATEST_FISCAL_YEAR,
    MAX_RESULT_SET,
    PAGE_SIZE,
)


def register(mcp: FastMCP) -> None:
    @mcp.resource(
        "nih-reporter://server-info",
        name="server_info",
        description=(
            "Server version, upstream API base URL, and key operational "
            "constraints (page size, result-set ceiling, fiscal year range)."
        ),
    )
    def server_info() -> str:
        return json.dumps(
            {
                "server": "nih-reporter-mcp",
                "version": __version__,
                "upstream_api": API_BASE,
                "constraints": {
                    "page_size": PAGE_SIZE,
                    "max_result_set": MAX_RESULT_SET,
                    "fiscal_year_range": [
                        EARLIEST_FISCAL_YEAR,
                        LATEST_FISCAL_YEAR,
                    ],
                },
                "notes": (
                    "No authentication required for the upstream RePORTER API. "
                    "Courtesy rate limit ~1 req/sec. Funding amounts available "
                    "only for NIH, CDC, FDA, and ACF projects."
                ),
            },
            indent=2,
        )
