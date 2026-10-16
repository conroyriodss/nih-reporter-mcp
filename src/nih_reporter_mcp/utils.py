"""Shared helpers: HTTP client, pagination, criteria builder, record mapper.

SSRF hardening (defense-in-depth):
  - Upstream hosts are hardcoded (api.reporter.nih.gov); never user-controllable.
  - follow_redirects=False prevents open-redirect abuse.
  - trust_env=False prevents environment-variable proxy injection.
  - Response bodies are size-capped (MAX_RESPONSE_BYTES) before JSON parsing.
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import os
import time
from urllib.parse import urlparse

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
MAX_STRING_LEN = 500        # default cap for free-text string params

# ── Validators ──────────────────────────────────────────────────────────────


def validate_topic(topic: str) -> str:
    topic = topic.strip()
    if not topic:
        raise ValueError("topic cannot be empty.")
    if len(topic) > MAX_STRING_LEN:
        raise ValueError(
            f"topic too long ({len(topic)} chars); max {MAX_STRING_LEN}."
        )
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


def validate_string_length(
    value: str, name: str, max_len: int = MAX_STRING_LEN,
) -> str:
    """Strip and cap the length of a free-text string parameter."""
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"{name} too long ({len(value)} chars); max {max_len}.")
    return value


# ── Host allowlist (SSRF defense-in-depth) ───────────────────────────────────

ALLOWED_HOSTS_REPORTER = frozenset({"api.reporter.nih.gov"})
ALLOWED_HOSTS_EUTILS = frozenset({"eutils.ncbi.nlm.nih.gov"})
ALLOWED_HOSTS_WSEARCH = frozenset({"wsearch.nlm.nih.gov"})


def validate_host(
    url: str, allowed_hosts: frozenset[str], service_name: str,
) -> None:
    """Assert the target URL's host is in the allowed set."""
    host = urlparse(url).hostname
    if host not in allowed_hosts:
        raise ValueError(
            f"{service_name}: host {host!r} not in allowed set "
            f"{sorted(allowed_hosts)}. This server only contacts "
            "fixed upstream origins."
        )


# ── HTTP + rate-limiting ────────────────────────────────────────────────────

_last_call_at = 0.0
_rate_lock = asyncio.Lock()


# ── Response cache (TTL-based, in-process) ──────────────────────────────────
# Caches raw API responses from post_json.  The cache key is a SHA-256 hash of
# (url, canonical-JSON-of-payload), so two calls with different payloads
# (different include_fields, criteria, offsets, etc.) never collide.
# Different funding_basis modes reuse the same cached raw response because
# funding_basis is a client-side aggregation parameter, not part of the API
# payload — aggregate_funding() processes the raw data differently for each
# mode, so correctness is preserved.

_CACHE_TTL = 900  # 15 minutes
_response_cache: dict[str, tuple[float, dict]] = {}


def _cache_key(url: str, payload: dict) -> str:
    """Deterministic cache key from URL + canonical JSON payload."""
    canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"))
    raw = f"{url}\0{canonical}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_disabled() -> bool:
    return os.environ.get("NIH_MCP_CACHE_DISABLED", "").strip() in ("1", "true", "yes")


def _evict_expired() -> None:
    """Remove entries older than TTL."""
    now = time.monotonic()
    expired = [k for k, (ts, _) in _response_cache.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _response_cache[k]


def cache_stats() -> dict:
    """Return cache statistics for observability."""
    _evict_expired()
    return {
        "entries": len(_response_cache),
        "disabled": _cache_disabled(),
        "ttl_seconds": _CACHE_TTL,
    }


def clear_cache() -> None:
    """Flush the entire response cache."""
    _response_cache.clear()


async def post_json(url: str, payload: dict) -> dict:
    """POST JSON to RePORTER with caching, rate-limiting, and retry on 429.

    Cache behaviour:
      - HIT:  returns instantly, bypasses rate limiter entirely.
      - MISS: rate-limited HTTP request, result stored in cache.
      - Disabled: set NIH_MCP_CACHE_DISABLED=1 in the environment.
    """
    global _last_call_at
    validate_host(url, ALLOWED_HOSTS_REPORTER, "RePORTER")

    use_cache = not _cache_disabled()
    key = _cache_key(url, payload) if use_cache else None

    # ── Cache check (skip rate limiter on hit) ────────────────────────
    if use_cache:
        _evict_expired()
        cached = _response_cache.get(key)
        if cached is not None:
            return cached[1]

    # ── Rate-limited HTTP request ─────────────────────────────────────
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
            result = resp.json()
            if use_cache and key is not None:
                _response_cache[key] = (time.monotonic(), result)
            return result
    raise RuntimeError("RePORTER rate limit hit repeatedly; please retry shortly.")


# ── Pagination ──────────────────────────────────────────────────────────────


MAX_PROVENANCE_IDS = 500  # cap source_record_ids to keep payloads reasonable


async def paginate_all(
    base_payload: dict,
    max_pages: int = MAX_PAGES,
    offset_ceiling: int = MAX_OFFSET_PROJECTS,
) -> tuple[list[dict], int, bool, int, list[int]]:
    """Paginate through all matching projects.

    Returns (results, total, complete, pages_fetched, appl_ids).
    appl_ids is capped at MAX_PROVENANCE_IDS for payload size.
    """
    all_results: list[dict] = []
    distinct_ids: set[int] = set()
    ordered_ids: list[int] = []  # insertion-order, for provenance
    total = 0
    pages_fetched = 0
    for page in range(max_pages):
        offset = page * PAGE_SIZE
        if offset > offset_ceiling:
            break
        payload = {**base_payload, "offset": offset, "limit": PAGE_SIZE}
        data = await post_json(PROJECTS_SEARCH, payload)
        # Validate upstream response structure (defend against malformed 200s)
        if not isinstance(data, dict) or "meta" not in data or "results" not in data:
            raise RuntimeError(
                "RePORTER returned a malformed response (missing 'meta' or "
                "'results' keys). The upstream API may be experiencing issues."
            )
        total = (data.get("meta") or {}).get("total", 0)
        results = data.get("results") or []
        all_results.extend(results)
        pages_fetched += 1
        # Track distinct appl_ids for completeness + provenance
        for r in results:
            aid = r.get("appl_id")
            if aid is not None and aid not in distinct_ids:
                distinct_ids.add(aid)
                if len(ordered_ids) < MAX_PROVENANCE_IDS:
                    ordered_ids.append(aid)
        if len(distinct_ids) >= total or not results:
            break
    # Completeness: count distinct IDs, not raw rows (page-boundary
    # duplicates inflate row count without adding new records).
    complete = len(distinct_ids) >= total if distinct_ids else len(all_results) >= total
    return all_results, total, complete, pages_fetched, ordered_ids


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
        abstract=rec.get("abstract_text"),
        start_date=rec.get("project_start_date"),
        end_date=rec.get("project_end_date"),
        reporter_url=PROJECT_URL.format(appl_id=appl_id) if appl_id else None,
    )


# ── Shared field lists ──────────────────────────────────────────────────────

INCLUDE_FIELDS = [
    "ApplId", "SubprojectId", "CoreProjectNum", "ProjectNum", "ProjectTitle",
    "AwardAmount", "FiscalYear", "Organization", "PrincipalInvestigators",
    "AgencyIcAdmin",
]
DETAIL_INCLUDE_FIELDS = INCLUDE_FIELDS + [
    "AbstractText", "ProjectStartDate", "ProjectEndDate",
]
AGG_FIELDS = [
    "ApplId", "SubprojectId", "AwardAmount",
    "Organization", "AgencyIcAdmin", "FiscalYear",
]


# ── Aggregation helpers ─────────────────────────────────────────────────────


class AggResult:
    """Result of aggregate_funding — a pure data container, not a Pydantic model,
    so that utils.py doesn't depend on models.py."""
    __slots__ = (
        "total_award", "record_count", "contributing_count",
        "records_with_missing_amount",
        "deduped_count", "subproject_excluded_count",
        "contributing_ids", "id_conflicts",
        "orphan_children",
    )

    def __init__(
        self,
        total_award: float,
        record_count: int,
        records_with_missing_amount: int,
        deduped_count: int,
        subproject_excluded_count: int,
        contributing_ids: list[int] | None = None,
        id_conflicts: list[int] | None = None,
        orphan_children: list[int] | None = None,
    ):
        self.total_award = total_award
        self.record_count = record_count  # eligible (post-exclusion, post-dedup, incl. null-amount)
        self.records_with_missing_amount = records_with_missing_amount
        self.deduped_count = deduped_count
        self.subproject_excluded_count = subproject_excluded_count
        self.contributing_ids = contributing_ids or []
        self.id_conflicts = id_conflicts or []
        # orphan_children: subproject appl_ids excluded in whole_award mode
        # whose parent core_project_num was NOT in the retrieved cohort.
        # Their funding may represent additional topical investment not
        # captured in the total.
        self.orphan_children = orphan_children or []
        # contributing_count: records that actually added a dollar amount
        # (= record_count - records_with_missing_amount)
        self.contributing_count = self.record_count - self.records_with_missing_amount

    @property
    def has_unresolved_conflicts(self) -> bool:
        """True if any appl_id appeared with differing amounts/FY/subproject."""
        return len(self.id_conflicts) > 0

    @property
    def is_exact(self) -> bool:
        """Conservative exactness: no missing amounts AND no unresolved
        duplicate conflicts AND no orphan children (whose parent awards
        are absent from the cohort).  Callers must ALSO check retrieval
        completeness."""
        return (self.records_with_missing_amount == 0
                and not self.has_unresolved_conflicts
                and len(self.orphan_children) == 0)


def aggregate_funding(
    records: list[dict],
    funding_basis: str = "whole_award",
) -> AggResult:
    """Sum award amounts from RePORTER records with correctness guarantees.

    funding_basis:
      - "whole_award" (default): exclude subproject records before summing
        (a record is a subproject if its subproject_id is set/non-null),
        deduplicate by appl_id, and track records with missing amounts
        separately (not zeroed).
      - "all_records": sum all records as-is (legacy behavior). Still
        deduplicates by appl_id and tracks missing amounts.

    Returns AggResult with:
      - contributing_ids: appl_ids that contributed to the dollar total
        (post-dedup, post-subproject-exclusion, non-null amount only).
      - id_conflicts: appl_ids seen multiple times with differing
        award_amount, fiscal_year, or subproject_id.  First occurrence
        is counted; subsequent are deduped.  Investigate manually.
      - orphan_children: subproject appl_ids excluded in whole_award mode
        whose parent core_project_num was NOT found among the cohort's
        parent records.
    """
    seen_appl_ids: dict[int, dict] = {}  # appl_id -> first occurrence info
    total_award = 0.0
    record_count = 0
    records_with_missing_amount = 0
    deduped_count = 0
    subproject_excluded_count = 0
    contributing_ids: list[int] = []
    id_conflicts: list[int] = []
    _conflict_seen: set[int] = set()
    # Track parent core_project_nums and excluded children for orphan detection
    _parent_projects: set[str] = set()
    _excluded_children: list[tuple[int, str | None]] = []  # (appl_id, core_project_num)

    for r in records:
        # ── Dedup by appl_id ──────────────────────────────────────────────────────
        appl_id = r.get("appl_id")
        if appl_id is not None:
            if appl_id in seen_appl_ids:
                # Identical data collapses silently; differing data is
                # flagged in id_conflicts (first-wins for the total).
                prev = seen_appl_ids[appl_id]
                if (r.get("award_amount") != prev.get("award_amount")
                        or r.get("fiscal_year") != prev.get("fiscal_year")
                        or r.get("subproject_id") != prev.get("subproject_id")):
                    if appl_id not in _conflict_seen:
                        _conflict_seen.add(appl_id)
                        id_conflicts.append(appl_id)
                deduped_count += 1
                continue
            seen_appl_ids[appl_id] = {
                "award_amount": r.get("award_amount"),
                "fiscal_year": r.get("fiscal_year"),
                "subproject_id": r.get("subproject_id"),
            }

        # ── Subproject exclusion (whole_award mode) ───────────────────
        if funding_basis == "whole_award":
            subproject_id = r.get("subproject_id")
            if subproject_id is not None:
                subproject_excluded_count += 1
                core_pn = r.get("core_project_num")
                if appl_id is not None:
                    _excluded_children.append((appl_id, core_pn))
                continue

        # ── Track parent project numbers ─────────────────────────────
        core_pn = r.get("core_project_num")
        if core_pn:
            _parent_projects.add(core_pn)

        # ── Sum with missing-amount tracking ──────────────────────────
        amount = r.get("award_amount")
        if amount is None:
            records_with_missing_amount += 1
        else:
            total_award += amount
            if appl_id is not None:
                contributing_ids.append(appl_id)
        record_count += 1

    # ── Orphan child detection ─────────────────────────────────────
    # Subprojects whose parent core_project_num was NOT found among the
    # cohort's parent records.  Their funding represents topical investment
    # associated with a matching component but NOT captured in the total
    # (because the parent's whole-award amount—which includes this child's
    # funding—is absent from the query results).
    orphan_children: list[int] = []
    if funding_basis == "whole_award" and _excluded_children:
        for child_id, child_cpn in _excluded_children:
            if child_cpn and child_cpn not in _parent_projects:
                orphan_children.append(child_id)

    return AggResult(
        total_award=round(total_award, 2),
        record_count=record_count,
        records_with_missing_amount=records_with_missing_amount,
        deduped_count=deduped_count,
        subproject_excluded_count=subproject_excluded_count,
        contributing_ids=contributing_ids,
        id_conflicts=id_conflicts,
        orphan_children=orphan_children,
    )
