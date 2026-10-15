"""list_publications_for_project — PubMed links produced by a project."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import MAX_OFFSET_PUBLICATIONS, PUBLICATIONS_SEARCH, PUBMED_URL
from nih_reporter_mcp.models import Publication, PublicationList
from nih_reporter_mcp.utils import post_json, validate_topic


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def list_publications_for_project(
        core_project_num: Annotated[str, Field(description="Core project number, e.g. 'R01AG012345'.")],
        limit: Annotated[int, Field(ge=1, le=500, description="Max publications to return (1-500).")] = 50,
    ) -> PublicationList:
        """Find publications (as PubMed links) produced by a specific NIH/HHS-funded project.

        RePORTER's publications endpoint returns only bare PMIDs -- no titles,
        journals, or author metadata.  Use get_publication_details with the
        pmids from this response to resolve them into full citations.
        """
        core_project_num = validate_topic(core_project_num)
        limit = min(limit, MAX_OFFSET_PUBLICATIONS + 1)
        payload = {"criteria": {"core_project_nums": [core_project_num]}, "offset": 0, "limit": limit}
        data = await post_json(PUBLICATIONS_SEARCH, payload)
        total = (data.get("meta") or {}).get("total", 0)
        results = data.get("results") or []

        pubs = [
            Publication(
                pmid=r["pmid"], core_project_num=r.get("coreproject"),
                appl_id=r.get("applid"), pubmed_url=PUBMED_URL.format(pmid=r["pmid"]),
            )
            for r in results if r.get("pmid")
        ]

        note = ("All linked publications returned." if total <= len(pubs) else
                f"Showing {len(pubs)} of {total} linked publications.")
        if total == 0:
            note = "No publications found linked to this project in RePORTER."

        return PublicationList(
            core_project_num=core_project_num, total_publications=total,
            returned=len(pubs), truncated=total > len(pubs), publications=pubs, note=note,
        )
