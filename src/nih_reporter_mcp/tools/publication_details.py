"""get_publication_details — resolve PubMed IDs into full citations via NCBI E-utilities."""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from nih_reporter_mcp.utils import ALLOWED_HOSTS_EUTILS, validate_host

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESUMMARY_URL = f"{EUTILS_BASE}/esummary.fcgi"
EUTILS_MIN_INTERVAL = 0.34  # ~3 req/sec without an API key; stay just under
EUTILS_TIMEOUT = 15.0
MAX_PMIDS_PER_CALL = 200  # E-utilities' own batch limit for esummary

_eutils_last_call_at = 0.0
_eutils_rate_lock = asyncio.Lock()


class PublicationDetail(BaseModel):
    pmid: int
    title: str | None = Field(None, description="Article title.")
    journal: str | None = Field(None, description="Journal name.")
    pub_date: str | None = Field(
        None,
        description="Publication date as reported by PubMed (format varies: may be year only, or year-month).",
    )
    authors: list[str] = Field(default_factory=list, description="Author names, in listed order.")
    doi: str | None = Field(None, description="Digital Object Identifier, if available.")
    pubmed_url: str


class PublicationDetailsResult(BaseModel):
    requested: int
    resolved: int
    not_found: list[int] = Field(
        default_factory=list, description="PMIDs that PubMed did not recognize."
    )
    publications: list[PublicationDetail]
    note: str


async def _eutils_get(params: dict) -> dict:
    """Rate-limited GET against NCBI E-utilities."""
    global _eutils_last_call_at
    async with _eutils_rate_lock:
        wait = EUTILS_MIN_INTERVAL - (time.monotonic() - _eutils_last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _eutils_last_call_at = time.monotonic()

    max_response_bytes = 10 * 1024 * 1024  # 10 MB safety cap

    validate_host(ESUMMARY_URL, ALLOWED_HOSTS_EUTILS, "E-utilities")

    async with httpx.AsyncClient(
        timeout=EUTILS_TIMEOUT,
        follow_redirects=False,   # SSRF: prevent open-redirect abuse
        trust_env=False,          # SSRF: ignore env-var proxy settings
    ) as client:
        try:
            resp = await client.get(ESUMMARY_URL, params=params)
        except httpx.TimeoutException as e:
            raise RuntimeError(
                "PubMed E-utilities request timed out. Try fewer PMIDs per call."
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"Network error contacting PubMed E-utilities: {e}") from e
        if resp.status_code == 429:
            raise RuntimeError(
                "PubMed E-utilities rate limit hit. Wait a moment and retry with fewer PMIDs."
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"PubMed E-utilities returned HTTP {resp.status_code}.")
        if len(resp.content) > max_response_bytes:
            raise RuntimeError(
                f"PubMed response too large ({len(resp.content):,} bytes). "
                "Try fewer PMIDs per call."
            )
        return resp.json()


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def get_publication_details(
        pmids: Annotated[
            list[int],
            Field(
                description=(
                    "PubMed IDs to resolve into full citation details, e.g. from "
                    "list_publications_for_project. Max 200 per call."
                )
            ),
        ],
    ) -> PublicationDetailsResult:
        """Resolve PubMed IDs into full citation details: title, journal, authors, date, DOI.

        Use this after list_publications_for_project, which only returns bare
        PMIDs (RePORTER's publications endpoint has no title/journal data).
        This tool queries PubMed directly via NCBI E-utilities to fill in the
        actual citation.  Unrecognized or malformed PMIDs are reported in
        'not_found' rather than causing the whole call to fail.
        """
        if not pmids:
            raise ValueError("pmids cannot be empty.")
        if len(pmids) > MAX_PMIDS_PER_CALL:
            raise ValueError(
                f"Too many PMIDs ({len(pmids)}); max {MAX_PMIDS_PER_CALL} per call."
            )

        params = {
            "db": "pubmed",
            "id": ",".join(str(p) for p in pmids),
            "retmode": "json",
        }
        data = await _eutils_get(params)
        result_block = data.get("result", {})
        uids = result_block.get("uids", [])

        publications: list[PublicationDetail] = []
        for uid in uids:
            rec = result_block.get(uid, {})
            if rec.get("error"):
                continue
            authors = [
                a.get("name") for a in rec.get("authors", []) if a.get("name")
            ]
            doi = None
            for aid in rec.get("articleids", []):
                if aid.get("idtype") == "doi":
                    doi = aid.get("value")
                    break
            publications.append(
                PublicationDetail(
                    pmid=int(uid),
                    title=rec.get("title"),
                    journal=rec.get("fulljournalname") or rec.get("source"),
                    pub_date=rec.get("pubdate"),
                    authors=authors,
                    doi=doi,
                    pubmed_url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                )
            )

        resolved_pmids = {p.pmid for p in publications}
        not_found = [p for p in pmids if p not in resolved_pmids]

        note = (
            "All requested PMIDs resolved."
            if not not_found
            else (
                f"{len(not_found)} of {len(pmids)} PMIDs could not be resolved "
                "(possibly withdrawn, embargoed, or invalid)."
            )
        )

        return PublicationDetailsResult(
            requested=len(pmids),
            resolved=len(publications),
            not_found=not_found,
            publications=publications,
            note=note,
        )
