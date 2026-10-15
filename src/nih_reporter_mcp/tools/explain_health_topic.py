"""explain_health_topic — plain-language health-topic explanations from MedlinePlus.

Queries the NLM Web Service API (wsearch.nlm.nih.gov) against the
healthTopics or healthTopicsSpanish database.  Returns the top-ranked
MedlinePlus health topic page: title, plain-language summary, and
authoritative source URL.  No API key required.

Upstream origin (fixed): wsearch.nlm.nih.gov
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Annotated
from xml.etree import ElementTree as ET

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from nih_reporter_mcp.utils import ALLOWED_HOSTS_WSEARCH, MAX_STRING_LEN, validate_host

WSEARCH_URL = "https://wsearch.nlm.nih.gov/ws/query"
WSEARCH_TIMEOUT = 15.0
WSEARCH_MIN_INTERVAL = 0.5  # conservative rate limit — no key, public service
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB safety cap

_wsearch_last_call_at = 0.0
_wsearch_rate_lock = asyncio.Lock()

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags from MedlinePlus search-highlight spans."""
    return _HTML_TAG_RE.sub("", text).strip()


class HealthTopicExplanation(BaseModel):
    query: str
    language: str
    title: str | None = None
    summary: str | None = Field(
        None,
        description=(
            "Plain-language health information summary from MedlinePlus "
            "(an authoritative NIH/NLM consumer health source)."
        ),
    )
    source_url: str | None = None
    found: bool
    note: str


async def _wsearch_get(params: dict) -> ET.Element:
    """Rate-limited GET against the NLM Web Search service, returning parsed XML."""
    global _wsearch_last_call_at
    async with _wsearch_rate_lock:
        wait = WSEARCH_MIN_INTERVAL - (time.monotonic() - _wsearch_last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _wsearch_last_call_at = time.monotonic()

    validate_host(WSEARCH_URL, ALLOWED_HOSTS_WSEARCH, "MedlinePlus")

    async with httpx.AsyncClient(
        timeout=WSEARCH_TIMEOUT,
        follow_redirects=False,  # SSRF: prevent open-redirect abuse
        trust_env=False,         # SSRF: ignore env-var proxy settings
    ) as client:
        try:
            resp = await client.get(WSEARCH_URL, params=params)
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "MedlinePlus health-topic request timed out. Try again shortly."
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Network error contacting MedlinePlus: {exc}"
            ) from exc
        if resp.status_code == 429:
            raise RuntimeError(
                "MedlinePlus rate limit hit. Wait a moment and retry."
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"MedlinePlus returned HTTP {resp.status_code}."
            )
        if len(resp.content) > MAX_RESPONSE_BYTES:
            raise RuntimeError(
                f"MedlinePlus response too large ({len(resp.content):,} bytes)."
            )
        return ET.fromstring(resp.content)


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def explain_health_topic(
        topic: Annotated[
            str,
            Field(
                description=(
                    "A health condition or topic in plain terms, e.g. "
                    "'diabetes', 'long covid', 'Parkinson\'s disease'."
                ),
            ),
        ],
        language: Annotated[
            str,
            Field(
                description="'en' for English or 'es' for Spanish.",
            ),
        ] = "en",
    ) -> HealthTopicExplanation:
        """Get an authoritative plain-language explanation of a health topic
        from MedlinePlus (the NIH National Library of Medicine's consumer
        health service), in English or Spanish.

        Use this to give a non-expert audience trustworthy background on a
        condition alongside NIH funding data.  This is general health
        education, NOT personalized medical advice -- it does not and cannot
        account for an individual's circumstances.
        """
        topic = topic.strip()
        if not topic:
            raise ValueError("topic cannot be empty.")
        if len(topic) > MAX_STRING_LEN:
            raise ValueError(
                f"topic too long ({len(topic)} chars); max {MAX_STRING_LEN}."
            )
        lang = language.strip().lower()
        if lang not in ("en", "es"):
            raise ValueError("language must be 'en' (English) or 'es' (Spanish).")

        db = "healthTopics" if lang == "en" else "healthTopicsSpanish"
        params = {"db": db, "term": topic, "retmax": "1"}
        root = await _wsearch_get(params)

        count = int(root.findtext("count") or "0")
        if count == 0:
            return HealthTopicExplanation(
                query=topic,
                language=lang,
                found=False,
                note=(
                    f"No MedlinePlus health topic matched '{topic}'"
                    + (" in Spanish" if lang == "es" else "")
                    + ". Try a broader or more common term "
                    "(e.g. 'heart disease' instead of 'ASCVD')."
                ),
            )

        doc = root.find(".//document")
        if doc is None:
            return HealthTopicExplanation(
                query=topic,
                language=lang,
                found=False,
                note="MedlinePlus returned a count but no document entries.",
            )

        source_url = doc.get("url")
        title = None
        summary = None

        for content_el in doc.findall("content"):
            name = content_el.get("name")
            raw = content_el.text or ""
            if name == "title" and not title:
                title = _strip_html(raw)
            elif name == "FullSummary" and not summary:
                summary = _strip_html(raw)
            elif name == "snippet" and not summary:
                # Fallback: use snippet if FullSummary is missing
                summary = _strip_html(raw)

        lang_label = "Spanish" if lang == "es" else "English"
        return HealthTopicExplanation(
            query=topic,
            language=lang,
            title=title,
            summary=summary,
            source_url=source_url,
            found=True,
            note=(
                f"Source: MedlinePlus ({lang_label}), an authoritative NIH/NLM "
                "consumer health resource. This is general health education, "
                "NOT personalized medical advice."
            ),
        )
