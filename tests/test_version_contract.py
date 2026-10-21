"""Contract: /version must report exactly what the MCP list endpoints return.

The test serves the real server app in-process (no network, no upstream API),
requests GET /version, then reads the live registries from the SAME FastMCP
instance through the list_* calls that back tools/list, prompts/list and
resources/list. It checks for equality only, so it guards against /version
drifting from the registries and keeps working when tools, prompts or
resources are added or removed. There are deliberately no literal counts here.
"""

from __future__ import annotations

import asyncio

from starlette.testclient import TestClient

from nih_reporter_mcp.app import mcp


async def _live_counts() -> dict[str, int]:
    return {
        "tools": len(await mcp.list_tools()),
        "prompts": len(await mcp.list_prompts()),
        "resources": len(await mcp.list_resources()),
    }


def test_version_counts_equal_live_registries():
    app = mcp.http_app()
    with TestClient(app) as client:  # runs the app's lifespan, like a started server
        resp = client.get("/version")
    assert resp.status_code == 200, resp.text
    reported = resp.json()

    live = asyncio.run(_live_counts())

    for key, n in live.items():
        # Non-vacuous: an empty registry would make 0 == 0 pass silently.
        assert n > 0, f"live {key} registry is empty"
        assert reported[key] == n, (
            f"/version reports {key}={reported[key]} but list_{key}() returns {n}"
        )
