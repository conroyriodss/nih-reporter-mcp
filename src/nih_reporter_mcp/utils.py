"""Shared helpers: HTTP client, pagination, criteria builder, record mapper.

SSRF hardening (defense-in-depth):
  - Upstream hosts are hardcoded (api.reporter.nih.gov); never user-controllable.
  - follow_redirects=False prevents open-redirect abuse.
  - trust_env=False prevents environment-variable proxy injection.
  - Response bodies are size-capped (MAX_RESPONSE_BYTES) before JSON parsing.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from nih_reporter_mcp.config import (
    EARLIEST_FISCAL_YEAR,
    LATEST_FISCAL_YEAR,
    MAX_OFFSET_PROJECTS,
    MAX_PAGES,
    MIN_REQUEST_INTERVAL,
    PAGE_SIZE,
    PROJECT_URL,
    PROJECTS_SEARCH,
    REQUEST_TIMEOUT,
)
from nih_reporter_mcp.models import ProjectSummary

# ── Hardening constants ─────────────────────────────────────────────────────

MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB — reject before JSON parsing
MAX_FISCAL_YEARS = 20       # cap pathological LLM-generated year lists
MAX_LIST_ITEMS = 20         # cap agencies / org_names list length

# ── Validators ──────────────────────────────────────────────────────────────


def validate_topic(topic: str) -> str:
    topic = topic.strip()
    if not topic:
        raise ValueError("topic cannot be empty.")
    return topic


def validate_fiscal_years(years: list[int] | None) -> list[int] | None:
    if not years:
        return years
    if len(years) > MAX_FISCAL_YEARS:
        raise ValueError(
            f"Too many fiscal years ({len(years)}); max {MAX_FISCAL_YEARS} per call."
        )
    bad = [y for y in years if not (EARLIEST_FISCAL_YEAR <= y <= LATEST_FISCAL_YEAR)]
    if bad:
        raise ValueError(
            f"Fiscal year(s) {bad} out of plausible range "
            f"({EARLIEST_FISCAL_YEAR}-{LATEST_FISCAL_YEAR})."
        )
    return years


def validate_list_length(items: list | None, name: str) -> list | None:
    """Guard against pathologically long list parameters from the LLM."""
    if items and len(items) > MAX_LIST_ITEMS:
        raise ValueError(
            f"Too many {name} ({len(items)}); max {MAX_LIST_ITEMS} per call."
        )
    return items


def validate_state(state: str | None) -> str | None:
    if not state:
        return None
    state = state.strip().upper()
    if len(state) != 2 or not state.isalpha():
        raise ValueError(f"org_state must be a two-letter US state code, got {state!r}.")
    return state


# ── HTTP + rate-limiting ────────────────────────────────────────────────────

_last_call_at = 0.0
_rate_lock = asyncio.Lock()


async def post_json(url: str, payload: dict) -> dict:
    """POST JSON to RePORTER with rate-limiting and retry on 429."""
    global _last_call_at
    async with _rate_lock:
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call_at = time.monotonic()

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=False,   # SSRF: prevent open-redirect abuse
        trust_env=False,          # SSRF: ignore env-var proxy settings
    ) as client:
        for attempt in range(2):
            try:
                resp = await client.post(url, json=payload)
            except httpx.TimeoutException as e:
                raise RuntimeError("RePORTER request timed out. Try narrowing the query.") from e
            except httpx.HTTPError as e:
                raise RuntimeError(f"Network error contacting RePORTER: {e}") from e

            if resp.status_code == 429 and attempt == 0:
                await asyncio.sleep(2.0)
                continue
            if resp.status_code == 400:
                raise ValueError(f"RePORTER rejected the request (400): {resp.text[:300]}")
            if resp.status_code == 403:
                raise ValueError(
                    "RePORTER blocked this request (403), likely because the search text "
                    "resembled a malicious pattern (e.g. SQL-like syntax). Try rephrasing."
                )
            if resp.status_code >= 400:
                raise RuntimeError(f"RePORTER returned an unexpected error (HTTP {resp.status_code}).")
            if len(resp.content) > MAX_RESPONSE_BYTES:
                raise RuntimeError(
                    f"Response too large ({len(resp.content):,} bytes, "
                    f"limit {MAX_RESPONSE_BYTES:,}). Narrow the query."
                )
            return resp.json()
    raise RuntimeError("RePORTER rate limit hit repeatedly; please retry shortly.")


# ── Pagination ──────────────────────────────────────────────────────────────


async def paginate_all(
    base_payload: dict,
    max_pages: int = MAX_PAGES,
    offset_ceiling: int = MAX_OFFSET_PROJECTS,
) -> tuple[list[dict], int, bool]:
    """Paginate through all matching projects. Returns (results, total, complete)."""
    all_results: list[dict] = []
    total = 0
    for page in range(max_pages):
        offset = page * PAGE_SIZE
        if offset > offset_ceiling:
            break
        payload = {**base_payload, "offset": offset, "limit": PAGE_SIZE}
        data = await post_json(PROJECTS_SEARCH, payload)
        total = (data.get("meta") or {}).get("total", 0)
        results = data.get("results") or []
        all_results.extend(results)
        if len(all_results) >= total or not results:
            break
    complete = len(all_results) >= total
    return all_results, total, complete


# ── Criteria builder ────────────────────────────────────────────────────────


def build_criteria(
    topic=None, fiscal_years=None, org_state=None, agencies=None,
    org_names=None, org_names_exact=None, pi_names=None,
    appl_ids=None, project_nums=None, spending_categories=None,
) -> dict:
    # Input-length guards (defense against pathological LLM-generated params)
    validate_list_length(agencies, "agencies")
    validate_list_length(org_names, "org_names")
    validate_list_length(org_names_exact, "org_names_exact")

    criteria: dict = {}
    if topic:
        criteria["advanced_text_search"] = {"operator": "and", "search_field": "all", "search_text": topic}
    if fiscal_years:
        criteria["fiscal_years"] = fiscal_years
    if org_state:
        criteria["org_states"] = [org_state]
    if agencies:
        criteria["agencies"] = [a.upper() for a in agencies]
    if org_names:
        criteria["org_names"] = org_names
    if org_names_exact:
        criteria["org_names_exact_match"] = org_names_exact
    if pi_names:
        criteria["pi_names"] = pi_names
    if appl_ids:
        criteria["appl_ids"] = appl_ids
    if project_nums:
        criteria["project_nums"] = project_nums
    if spending_categories:
        criteria["spending_categories"] = {"values": spending_categories, "match_all": False}
    return criteria


# ── Record mapper ───────────────────────────────────────────────────────────


def to_summary(rec: dict) -> ProjectSummary:
    """Map a raw RePORTER project record to a ProjectSummary."""
    org = rec.get("organization") or {}
    ic = rec.get("agency_ic_admin") or {}
    pis = [p.get("full_name") for p in (rec.get("principal_investigators") or []) if p.get("full_name")]
    appl_id = rec.get("appl_id")
    return ProjectSummary(
        core_project_num=rec.get("core_project_num") or rec.get("project_num"),
        title=rec.get("project_title"),
        award_amount=rec.get("award_amount"),
        fiscal_year=rec.get("fiscal_year"),
        organization=org.get("org_name"),
        org_state=org.get("org_state"),
        principal_investigators=pis,
        administering_ic=ic.get("abbreviation") or ic.get("name"),
        reporter_url=PROJECT_URL.format(appl_id=appl_id) if appl_id else None,
    )


# ── Shared field lists ──────────────────────────────────────────────────────

INCLUDE_FIELDS = [
    "ApplId", "CoreProjectNum", "ProjectNum", "ProjectTitle", "AwardAmount",
    "FiscalYear", "Organization", "PrincipalInvestigators", "AgencyIcAdmin",
]
AGG_FIELDS = ["AwardAmount", "Organization", "AgencyIcAdmin", "FiscalYear"]
