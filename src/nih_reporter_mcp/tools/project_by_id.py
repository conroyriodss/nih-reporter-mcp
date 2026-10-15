"""get_project_by_id — direct lookup by appl_id or core_project_num."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import PROJECTS_SEARCH
from nih_reporter_mcp.models import SearchResult
from nih_reporter_mcp.utils import INCLUDE_FIELDS, build_criteria, post_json, to_summary, validate_string_length


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def get_project_by_id(
        appl_id: Annotated[int | None, Field(description="Application ID. Use this OR core_project_num.")] = None,
        core_project_num: Annotated[str | None, Field(description="Core project number. Use this OR appl_id.")] = None,
    ) -> SearchResult:
        """Look up one or more specific NIH/HHS projects directly by ID."""
        if not appl_id and not core_project_num:
            raise ValueError("Provide either appl_id or core_project_num.")
        if core_project_num:
            core_project_num = validate_string_length(
                core_project_num, "core_project_num",
            )

        payload = {
            "criteria": build_criteria(
                appl_ids=[appl_id] if appl_id else None,
                project_nums=[core_project_num] if core_project_num else None,
            ),
            "include_fields": INCLUDE_FIELDS,
            "offset": 0,
            "limit": 25,
        }
        data = await post_json(PROJECTS_SEARCH, payload)
        total = (data.get("meta") or {}).get("total", 0)
        results = data.get("results") or []
        projects = [to_summary(r) for r in results]
        return SearchResult(
            total_matching_projects=total, returned=len(projects),
            truncated=total > len(projects), projects=projects,
        )
