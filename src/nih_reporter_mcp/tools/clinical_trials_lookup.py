"""STUB: not yet implemented.

Planned: query ClinicalTrials.gov v2 API to find trials associated with a
core_project_num or PI name, connecting RePORTER funding data to
patient-facing trial status.

This file is an intentional placeholder — it documents a roadmap item
without exposing a broken tool to MCP clients.  It is deliberately NOT
registered in tools/__init__.py.

See docs/roadmap.md for the full Tier 2 feature plan.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:  # noqa: ARG001
    """Register clinical trials lookup tool.

    TODO: Implement ClinicalTrials.gov v2 API integration.
    - Endpoint: https://clinicaltrials.gov/api/v2/studies
    - Link trials to RePORTER grants via NCT numbers or PI names.
    - Return trial phase, status, enrollment, conditions, and interventions.
    - Respect rate limit: 10 requests/minute without an API key.
    """
    raise NotImplementedError(
        "clinical_trials_lookup is a Tier 2 roadmap item. "
        "See docs/roadmap.md for planned implementation."
    )
