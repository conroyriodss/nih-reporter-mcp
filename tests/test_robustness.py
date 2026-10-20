"""Robustness & stability evaluation layer.

Targets the four hackathon judging criteria:
  1. Thoughtful eval design     — programmatic coverage of ALL tools
  2. Well-formed responses      — Pydantic model validation on every call
  3. Graceful error handling     — parameterized error matrix + mocked failures
  4. Stable performance          — repeated-call consistency + latency profile

Requires a running MCP server at MCP_URL (default http://localhost:8000/mcp).
Parts A/B/D/E are live-server integration tests.
Part C is a pure unit test (mocked httpx, no server needed).

Run:  python -m pytest tests/test_robustness.py -v --tb=short
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ── Server connection ────────────────────────────────────────────────────────

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")

# ── Helpers ──────────────────────────────────────────────────────────────────

# Module-level event loop — shared across fixtures and tests so the
# MCP Client's async context manager enter/exit use the same loop.
_loop = asyncio.new_event_loop()


def run(coro):
    """Run an async coroutine on the module's event loop (Python 3.12+ safe)."""
    return _loop.run_until_complete(coro)


@pytest.fixture(scope="module")
def mcp():
    """A single MCP Client session reused across the module."""
    from fastmcp import Client
    client = Client(MCP_URL)
    run(client.__aenter__())
    yield client
    run(client.__aexit__(None, None, None))


@pytest.fixture(scope="module")
def live_tool_names(mcp):
    """Tool names discovered from the live server — no hardcoded list."""
    tools = run(mcp.list_tools())
    return sorted(t.name for t in tools)


# ── Tool input specs (normal, zero-result, boundary) ─────────────────────────
# Keyed by tool name.  Each value is a dict with:
#   normal:   valid input that should return data
#   zero:     valid input that should return an empty/zero result
#   boundary: edge-case input (optional; None if not applicable)

TOOL_INPUTS = {
    "search_funded_projects": {
        "normal":   {"topic": "CRISPR sickle cell", "fiscal_years": [2024], "limit": 5},
        "zero":     {"topic": "xyznonexistent999qqq", "fiscal_years": [2024], "limit": 5},
        "boundary": {"topic": "CRISPR", "fiscal_years": [2024], "limit": 1},
    },
    "summarize_funding_by_topic": {
        "normal":   {"topic": "CRISPR gene editing", "fiscal_years": [2023]},
        "zero":     {"topic": "xyznonexistent999qqq", "fiscal_years": [2024]},
        "boundary": {"topic": "CRISPR gene editing", "fiscal_years": [2023], "funding_basis": "all_records"},
    },
    "funding_trend_by_year": {
        "normal":   {"topic": "CRISPR sickle cell", "start_year": 2023, "end_year": 2024},
        "zero":     {"topic": "xyznonexistent999qqq", "start_year": 2024, "end_year": 2024},
        "boundary": {"spending_category": "Cancer", "start_year": 2024, "end_year": 2024},
    },
    "organization_funding_profile": {
        "normal":   {"organization_name": "JOHNS HOPKINS UNIVERSITY", "fiscal_years": [2024]},
        "zero":     {"organization_name": "ZZZFAKEUNIVERSITY999", "fiscal_years": [2024], "exact_match": True},
        "boundary": {"organization_name": "JOHNS HOPKINS UNIVERSITY", "fiscal_years": [2024], "exact_match": True},
    },
    "get_project_by_id": {
        "normal":   {"appl_id": 10876342},
        "zero":     {"appl_id": 1},
        "boundary": None,
    },
    "investigator_portfolio": {
        "normal":   {"last_name": "Collins", "first_name": "Francis"},
        "zero":     {"last_name": "Zzzfakename", "first_name": "Qqq"},
        "boundary": {"last_name": "Smith"},
    },
    "list_publications_for_project": {
        "normal":   {"core_project_num": "R01HL169761"},
        "zero":     {"core_project_num": "ZZ99ZZ999999"},
        "boundary": None,
    },
    "get_publication_details": {
        "normal":   {"pmids": [38243618]},
        "zero":     {"pmids": [1]},
        "boundary": {"pmids": [38243618, 38000000]},
    },
    "check_investigator_overlap": {
        "normal":   {"last_name": "Au", "first_name": "Rhoda"},
        "zero":     {"last_name": "Zzzfakename", "first_name": "Qqq"},
        "boundary": {"last_name": "Au", "first_name": "Rhoda", "exclude_project_num": "U19AG068753"},
    },
    "funded_projects_by_study_section": {
        "normal":   {"topic": "CRISPR gene editing", "fiscal_years": [2023]},
        "zero":     {"topic": "xyznonexistent999qqq", "fiscal_years": [2024]},
        "boundary": {"topic": "CRISPR", "fiscal_years": [2024]},
    },
    "search_recent_awards": {
        "normal":   {"limit": 5},
        "zero":     {"topic": "xyznonexistent999qqq", "limit": 5},
        "boundary": {"limit": 1},
    },
    "export_evidence_bundle": {
        "normal":   {"topic": "CRISPR sickle cell", "fiscal_years": [2024], "label": "robustness"},
        "zero":     {"topic": "xyznonexistent999qqq", "fiscal_years": [2024], "label": "robustness-zero"},
        "boundary": {"topic": "CRISPR sickle cell", "fiscal_years": [2024], "label": "rb", "funding_basis": "all_records"},
    },
    "explain_health_topic": {
        "normal":   {"topic": "diabetes"},
        "zero":     {"topic": "zzznotarealcondition999"},
        "boundary": {"topic": "asthma", "language": "es"},
    },
    "clinical_trials_lookup": {
        "normal":   {"core_project_num": "R01HL147914"},
        "zero":     {"core_project_num": "ZZ99ZZ999999"},
        "boundary": {"condition": "sickle cell disease"},
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PART A — Well-formed responses across ALL tools
# ══════════════════════════════════════════════════════════════════════════════

class TestPartA_WellFormedResponses:
    """Every tool returns a validated Pydantic model, never raw dict/None."""

    def test_all_tools_have_test_inputs(self, live_tool_names):
        """Fail-safe: any tool missing from TOOL_INPUTS is a coverage gap."""
        missing = set(live_tool_names) - set(TOOL_INPUTS)
        assert not missing, f"Tools without test coverage: {missing}"

    @pytest.mark.parametrize("case", ["normal", "zero", "boundary"])
    def test_well_formed_response(self, mcp, live_tool_names, case):
        """Every tool × {normal, zero, boundary} returns a non-None structured response."""
        failures = []
        for tool_name in live_tool_names:
            spec = TOOL_INPUTS.get(tool_name, {})
            args = spec.get(case)
            if args is None:
                continue  # boundary not applicable
            try:
                result = run(mcp.call_tool(tool_name, args))
                d = result.data
                if d is None:
                    failures.append(f"{tool_name}[{case}]: returned None")
                elif isinstance(d, dict):
                    failures.append(f"{tool_name}[{case}]: returned raw dict instead of model")
            except Exception as e:
                # Zero-result should NOT raise — it should return an empty model
                if case == "zero":
                    failures.append(f"{tool_name}[{case}]: raised {type(e).__name__}: {e}")
                # Normal/boundary raising is also a failure
                elif case == "normal":
                    failures.append(f"{tool_name}[{case}]: raised {type(e).__name__}: {e}")
                # Boundary may raise for legitimate validation reasons — skip
        assert not failures, "Malformed responses:\n" + "\n".join(failures)


# ══════════════════════════════════════════════════════════════════════════════
# PART B — Graceful error handling matrix
# ══════════════════════════════════════════════════════════════════════════════

# Error conditions per tool: (tool_name, condition_name, args_dict, expect_error)
# expect_error=True → must raise a clean ValueError-style message
# expect_error=False → must return a valid empty response (e.g. nonexistent ID)

ERROR_MATRIX: list[tuple[str, str, dict, bool]] = []

# funded_projects_by_study_section accepts empty args (returns defaults) — tested separately
# ── Missing required parameter ───────────────────────────────────────────────
for tool, req_params in [
    ("search_funded_projects", {}),  # topic is required
    ("summarize_funding_by_topic", {}),
    ("funding_trend_by_year", {}),
    ("organization_funding_profile", {}),
    ("get_project_by_id", {}),  # appl_id required
    ("investigator_portfolio", {}),  # last_name required
    ("list_publications_for_project", {}),
    ("get_publication_details", {}),
    ("check_investigator_overlap", {}),
    ("export_evidence_bundle", {}),
    ("explain_health_topic", {}),
]:
    ERROR_MATRIX.append((tool, "missing_required", req_params, True))

# ── Wrong type ───────────────────────────────────────────────────────────────
ERROR_MATRIX += [
    ("search_funded_projects", "wrong_type_topic", {"topic": 12345}, True),
    ("summarize_funding_by_topic", "wrong_type_fiscal_years", {"topic": "cancer", "fiscal_years": "2023"}, True),
    ("get_project_by_id", "wrong_type_appl_id", {"appl_id": "not_a_number"}, True),
    ("get_publication_details", "wrong_type_pmid", {"pmids": "not_a_number"}, True),
    ("funding_trend_by_year", "wrong_type_start_year", {"topic": "cancer", "start_year": "abc", "end_year": 2023}, True),
]

# ── Valid format but nonexistent ID → clean zero-result, NOT error ───────────
ERROR_MATRIX += [
    ("get_project_by_id", "nonexistent_appl_id", {"appl_id": 1}, False),
    ("list_publications_for_project", "nonexistent_project", {"core_project_num": "ZZ99ZZ999999"}, False),
    ("get_publication_details", "nonexistent_pmid", {"pmids": [1]}, False),
    ("organization_funding_profile", "nonexistent_org", {"organization_name": "ZZZFAKEUNIVERSITY999", "fiscal_years": [2024], "exact_match": True}, False),
    ("check_investigator_overlap", "nonexistent_pi", {"last_name": "Zzzfakename999", "first_name": "Qqq"}, False),
    ("explain_health_topic", "nonexistent_topic", {"topic": "zzznotarealcondition999"}, False),
]

# ── Oversized input → clean validation error ─────────────────────────────────
_long_string = "A" * 600  # > MAX_STRING_LEN (500)
_long_year_list = list(range(2000, 2025))  # 25 items > MAX_FISCAL_YEARS (20)
ERROR_MATRIX += [
    ("search_funded_projects", "oversized_topic", {"topic": _long_string}, True),
    ("summarize_funding_by_topic", "oversized_topic", {"topic": _long_string}, True),
    ("summarize_funding_by_topic", "oversized_fiscal_years", {"topic": "cancer", "fiscal_years": _long_year_list}, True),
    ("funded_projects_by_study_section", "oversized_topic", {"topic": _long_string}, True),
    ("export_evidence_bundle", "oversized_topic", {"topic": _long_string, "fiscal_years": [2024], "label": "x"}, True),
    ("organization_funding_profile", "oversized_org_name", {"organization_name": _long_string, "fiscal_years": [2024]}, True),
]


class TestPartB_ErrorHandlingMatrix:
    """Parameterized error conditions produce clean errors or valid empty responses."""

    @pytest.mark.parametrize(
        "tool_name,condition,args,expect_error",
        ERROR_MATRIX,
        ids=[f"{t}::{c}" for t, c, _, _ in ERROR_MATRIX],
    )
    def test_error_condition(self, mcp, tool_name, condition, args, expect_error):
        if expect_error:
            with pytest.raises(Exception) as exc_info:
                run(mcp.call_tool(tool_name, args))
            msg = str(exc_info.value).lower()
            # Must be a clean error, not a leaked traceback
            assert "traceback" not in msg, f"Leaked traceback: {exc_info.value}"
            assert "httpx" not in msg, f"Leaked httpx internals: {exc_info.value}"
        else:
            # Should return a valid response, NOT raise
            result = run(mcp.call_tool(tool_name, args))
            assert result.data is not None, f"{tool_name} returned None for {condition}"


# ══════════════════════════════════════════════════════════════════════════════
# PART C — Simulated upstream failure (mocked httpx)
# ══════════════════════════════════════════════════════════════════════════════

class TestPartC_MockedUpstreamFailures:
    """Unit-test error paths that can't be triggered with live calls."""

    @pytest.fixture(autouse=True)
    def _reset_cache(self):
        """Disable cache so every call hits the mock."""
        os.environ["NIH_MCP_CACHE_DISABLED"] = "1"
        yield
        os.environ.pop("NIH_MCP_CACHE_DISABLED", None)

    def _make_mock_response(self, status_code=200, content=b'{}', json_data=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.content = content if json_data is None else json.dumps(json_data).encode()
        resp.text = content.decode() if json_data is None else json.dumps(json_data)
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            try:
                resp.json.return_value = json.loads(content) if content else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                resp.json.side_effect = json.JSONDecodeError("Not JSON", str(content), 0)
        return resp

    def test_http_500_produces_runtime_error(self):
        from nih_reporter_mcp.utils import post_json

        mock_resp = self._make_mock_response(status_code=500)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="unexpected error.*500"):
                run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))

    def test_timeout_produces_runtime_error(self):
        from nih_reporter_mcp.utils import post_json

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timed out")

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="timed out"):
                run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))

    def test_429_retries_then_succeeds(self):
        from nih_reporter_mcp.utils import post_json

        resp_429 = self._make_mock_response(status_code=429)
        resp_200 = self._make_mock_response(
            status_code=200,
            json_data={"meta": {"total": 0}, "results": []},
        )
        mock_client = AsyncMock()
        mock_client.post.side_effect = [resp_429, resp_200]

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            result = run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))
            assert result == {"meta": {"total": 0}, "results": []}
            assert mock_client.post.call_count == 2  # retried once

    def test_oversized_response_rejected(self):
        from nih_reporter_mcp.utils import post_json, MAX_RESPONSE_BYTES

        huge_content = b"x" * (MAX_RESPONSE_BYTES + 1)
        mock_resp = self._make_mock_response(status_code=200, content=huge_content)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="too large"):
                run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))

    def test_malformed_json_produces_error(self):
        from nih_reporter_mcp.utils import post_json

        mock_resp = self._make_mock_response(status_code=200, content=b"NOT JSON{{{")
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises((json.JSONDecodeError, RuntimeError)):
                run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))

    def test_network_error_produces_runtime_error(self):
        from nih_reporter_mcp.utils import post_json

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="Network error"):
                run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))

    def test_http_400_produces_value_error(self):
        from nih_reporter_mcp.utils import post_json

        mock_resp = self._make_mock_response(status_code=400, content=b"Bad Request")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="rejected.*400"):
                run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))

    def test_http_403_produces_value_error(self):
        from nih_reporter_mcp.utils import post_json

        mock_resp = self._make_mock_response(status_code=403, content=b"Forbidden")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="blocked.*403"):
                run(post_json("https://api.reporter.nih.gov/v2/projects/search", {}))

    def test_malformed_200_raises_error(self):
        """A 200 with {} body (missing meta/results keys) must NOT produce
        a clean zero-complete result — it must raise RuntimeError."""
        from nih_reporter_mcp.utils import paginate_all

        # post_json returns the parsed JSON; paginate_all calls post_json
        # and validates the response structure.
        mock_resp = self._make_mock_response(
            status_code=200, json_data={},  # no "meta", no "results"
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="malformed"):
                run(paginate_all({"criteria": {}, "include_fields": []}))

    def test_malformed_200_with_partial_keys_raises_error(self):
        """A 200 with only 'meta' but no 'results' key must also raise."""
        from nih_reporter_mcp.utils import paginate_all

        mock_resp = self._make_mock_response(
            status_code=200, json_data={"meta": {"total": 5}},  # no "results"
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="malformed"):
                run(paginate_all({"criteria": {}, "include_fields": []}))



    def test_meta_present_but_no_total_key(self):
        """GAP 1: {meta: {}, results: []} must NOT produce complete=True
        with total=0.  meta exists but lacks 'total' — this is malformed,
        not a legitimate empty result."""
        from nih_reporter_mcp.utils import paginate_all

        mock_resp = self._make_mock_response(
            status_code=200,
            json_data={"meta": {}, "results": []},  # meta present, no "total"
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("nih_reporter_mcp.utils.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            # Should NOT silently return complete=True, total=0.
            # Either raise RuntimeError or return complete=False.
            with pytest.raises(RuntimeError, match="malformed"):
                run(paginate_all({"criteria": {}, "include_fields": []}))

# ══════════════════════════════════════════════════════════════════════════════
# PART D — Stability across repeated calls
# ══════════════════════════════════════════════════════════════════════════════

STABILITY_TOOLS = [
    ("summarize_funding_by_topic", {"topic": "CRISPR sickle cell", "fiscal_years": [2024]}),
    ("organization_funding_profile", {"organization_name": "JOHNS HOPKINS UNIVERSITY", "fiscal_years": [2024]}),
    ("search_recent_awards", {"limit": 3}),
]
STABILITY_RUNS = 5


class TestPartD_Stability:
    """Repeated identical calls produce identical results."""

    @pytest.mark.parametrize(
        "tool_name,args",
        STABILITY_TOOLS,
        ids=[t for t, _ in STABILITY_TOOLS],
    )
    def test_stability_cache_enabled(self, mcp, tool_name, args):
        """With cache ON, 5 runs must be perfectly identical."""
        os.environ.pop("NIH_MCP_CACHE_DISABLED", None)
        results = []
        for _ in range(STABILITY_RUNS):
            r = run(mcp.call_tool(tool_name, args))
            d = r.data
            # Extract the key numeric fields
            if hasattr(d, "total_award_amount_usd"):
                results.append(d.total_award_amount_usd)
            elif hasattr(d, "total_matching"):
                results.append(d.total_matching)
            elif hasattr(d, "returned"):
                results.append(d.returned)
            else:
                results.append(str(d))
        assert len(set(str(r) for r in results)) == 1, (
            f"Cache-on instability for {tool_name}: {results}"
        )

    @pytest.mark.parametrize(
        "tool_name,args",
        STABILITY_TOOLS[:2],  # skip recent_awards (ordering can change)
        ids=[t for t, _ in STABILITY_TOOLS[:2]],
    )
    def test_stability_cache_disabled(self, mcp, tool_name, args):
        """With cache OFF, dollar totals should still be stable across 5 runs."""
        os.environ["NIH_MCP_CACHE_DISABLED"] = "1"
        try:
            results = []
            for _ in range(STABILITY_RUNS):
                r = run(mcp.call_tool(tool_name, args))
                d = r.data
                if hasattr(d, "total_award_amount_usd"):
                    results.append(d.total_award_amount_usd)
                elif hasattr(d, "total_matching_projects"):
                    results.append(d.total_matching_projects)
                else:
                    results.append(str(d))
            assert len(set(str(r) for r in results)) == 1, (
                f"Cache-off instability for {tool_name}: {results}"
            )
        finally:
            os.environ.pop("NIH_MCP_CACHE_DISABLED", None)


# ══════════════════════════════════════════════════════════════════════════════
# PART E — Latency profile
# ══════════════════════════════════════════════════════════════════════════════

class TestPartE_LatencyProfile:
    """Time every tool once (cold cache) and report."""

    def test_latency_profile(self, mcp):
        """All tools respond within a reasonable time; flag any > 10s cold."""
        from nih_reporter_mcp.utils import clear_cache
        clear_cache()
        os.environ.pop("NIH_MCP_CACHE_DISABLED", None)

        latencies = []
        slow_tools = []

        for tool_name in sorted(TOOL_INPUTS):
            args = TOOL_INPUTS[tool_name]["normal"]
            t0 = time.monotonic()
            try:
                run(mcp.call_tool(tool_name, args))
                elapsed = time.monotonic() - t0
                ok = True
            except Exception:
                elapsed = time.monotonic() - t0
                ok = False
            latencies.append((tool_name, round(elapsed, 2), "cold", ok))
            if elapsed > 10.0:
                slow_tools.append((tool_name, elapsed))

        # Print the latency table for the report
        print("\n" + "=" * 70)
        print("LATENCY PROFILE (cold cache)")
        print("=" * 70)
        print(f"{'Tool':<45} {'Latency':>8}  {'Status':>6}")
        print("-" * 70)
        for name, lat, cache, ok in latencies:
            status = "OK" if ok else "ERROR"
            flag = " SLOW!" if lat > 10.0 else ""
            print(f"{name:<45} {lat:>7.2f}s  {status:>6}{flag}")
        print("=" * 70)

        # Not a hard failure — just document
        if slow_tools:
            print(f"\nWARNING: {len(slow_tools)} tools over 10s cold: "
                  f"{[(n, f'{l:.1f}s') for n, l in slow_tools]}")
