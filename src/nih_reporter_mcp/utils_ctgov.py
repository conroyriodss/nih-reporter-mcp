"""ClinicalTrials.gov v2 HTTP client — hardened, rate-limited, cached.

Mirrors the existing RePORTER client pattern in utils.py:
  - Host allowlist (clinicaltrials.gov only)
  - follow_redirects=False, trust_env=False
  - Response-size cap (5 MB)
  - Per-request rate limiting (0.5 s min interval)
  - TTL response cache (15 min)

SSRF hardening: the only user-controllable input that reaches a URL is the
NCT ID or grant ID, which is appended as a path segment or query parameter
to the hardcoded base URL.  validate_host() catches any drift.
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import time

import httpx

from nih_reporter_mcp.config import (
    CTGOV_MAX_RESPONSE_BYTES,
    CTGOV_MIN_REQUEST_INTERVAL,
    CTGOV_STUDIES,
    CTGOV_STUDY,
    CTGOV_TIMEOUT,
)
from nih_reporter_mcp.utils import (
    ALLOWED_HOSTS_CTGOV,
    _cache_disabled,
    _CACHE_TTL,
    validate_host,
)

# ── Rate limiting (independent from RePORTER limiter) ─────────────────────

_ctgov_last_call = 0.0
_ctgov_lock = asyncio.Lock()

# ── Response cache (shared TTL, separate store) ──────────────────────────

_ctgov_cache: dict[str, tuple[float, dict]] = {}


def _ctgov_cache_key(url: str, params: dict | None) -> str:
    canonical = _json.dumps(params or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{url}\0{canonical}".encode()).hexdigest()


def _ctgov_evict_expired() -> None:
    now = time.monotonic()
    expired = [k for k, (ts, _) in _ctgov_cache.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _ctgov_cache[k]


def clear_ctgov_cache() -> None:
    _ctgov_cache.clear()


async def ctgov_get(url: str, params: dict | None = None) -> dict:
    """GET from ClinicalTrials.gov v2 with hardening, cache, and rate limit.

    Raises RuntimeError on network/timeout/size errors,
    ValueError on 400-class client errors.
    """
    global _ctgov_last_call
    validate_host(url, ALLOWED_HOSTS_CTGOV, "ClinicalTrials.gov")

    use_cache = not _cache_disabled()
    key = _ctgov_cache_key(url, params) if use_cache else None

    if use_cache:
        _ctgov_evict_expired()
        cached = _ctgov_cache.get(key)  # type: ignore[arg-type]
        if cached is not None:
            return cached[1]

    # Rate limit
    async with _ctgov_lock:
        wait = CTGOV_MIN_REQUEST_INTERVAL - (time.monotonic() - _ctgov_last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _ctgov_last_call = time.monotonic()

    async with httpx.AsyncClient(
        timeout=CTGOV_TIMEOUT,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.TimeoutException as e:
            raise RuntimeError(
                "ClinicalTrials.gov request timed out. Try a more specific query."
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(
                f"Network error contacting ClinicalTrials.gov: {e}"
            ) from e

        if resp.status_code == 404:
            return {"studies": [], "totalCount": 0, "nextPageToken": None}
        if resp.status_code == 400:
            raise ValueError(
                f"ClinicalTrials.gov rejected the request (400): {resp.text[:300]}"
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"ClinicalTrials.gov returned HTTP {resp.status_code}."
            )
        if len(resp.content) > CTGOV_MAX_RESPONSE_BYTES:
            raise RuntimeError(
                f"Response too large ({len(resp.content):,} bytes, "
                f"limit {CTGOV_MAX_RESPONSE_BYTES:,}). Narrow the query."
            )

        result = resp.json()
        if use_cache and key is not None:
            _ctgov_cache[key] = (time.monotonic(), result)
        return result


async def fetch_study(nct_id: str) -> dict | None:
    """Fetch a single study by NCT ID.  Returns None if not found."""
    url = CTGOV_STUDY.format(nct_id=nct_id)
    data = await ctgov_get(url)
    if not data or "protocolSection" not in data:
        return None
    return data


async def search_studies_by_grant(grant_id: str, max_results: int = 20) -> list[dict]:
    """Search ClinicalTrials.gov for studies linked to a grant ID.

    Uses query.id which performs exact match against orgStudyIdInfo.id
    and secondaryIdInfos[].id.
    """
    data = await ctgov_get(
        CTGOV_STUDIES,
        params={
            "query.id": grant_id,
            "countTotal": "true",
            "pageSize": min(max_results, 20),
        },
    )
    return data.get("studies") or []


async def search_studies_by_condition(
    condition: str, max_results: int = 20,
) -> list[dict]:
    """Search ClinicalTrials.gov for studies matching a condition/topic."""
    data = await ctgov_get(
        CTGOV_STUDIES,
        params={
            "query.cond": condition,
            "countTotal": "true",
            "pageSize": min(max_results, 20),
        },
    )
    return data.get("studies") or []
