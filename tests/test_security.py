"""Security unit tests — host allowlists and input-size guards.

Runs without the MCP server (direct function/module calls). Execute with:

    PYTHONPATH=src pytest tests/test_security.py -v
"""

from __future__ import annotations

import pytest

from nih_reporter_mcp.utils import (
    ALLOWED_HOSTS_CTGOV,
    ALLOWED_HOSTS_EUTILS,
    ALLOWED_HOSTS_REPORTER,
    ALLOWED_HOSTS_WSEARCH,
    MAX_STRING_LEN,
    validate_host,
    validate_string_length,
    validate_topic,
    validate_list_length,
    validate_fiscal_years,
)


# ── Host allowlist tests ────────────────────────────────────────────────────


class TestHostAllowlist:
    """Every HTTP client must reject URLs whose host is not in the allowlist."""

    def test_reporter_allows_correct_host(self):
        # Should not raise
        validate_host(
            "https://api.reporter.nih.gov/v2/projects/search",
            ALLOWED_HOSTS_REPORTER,
            "RePORTER",
        )

    def test_reporter_rejects_wrong_host(self):
        with pytest.raises(ValueError, match="not in allowed set"):
            validate_host(
                "https://evil.example.com/v2/projects/search",
                ALLOWED_HOSTS_REPORTER,
                "RePORTER",
            )

    def test_eutils_allows_correct_host(self):
        validate_host(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            ALLOWED_HOSTS_EUTILS,
            "E-utilities",
        )

    def test_eutils_rejects_wrong_host(self):
        with pytest.raises(ValueError, match="not in allowed set"):
            validate_host(
                "https://evil.example.com/entrez/eutils/esummary.fcgi",
                ALLOWED_HOSTS_EUTILS,
                "E-utilities",
            )

    def test_wsearch_allows_correct_host(self):
        validate_host(
            "https://wsearch.nlm.nih.gov/ws/query",
            ALLOWED_HOSTS_WSEARCH,
            "MedlinePlus",
        )

    def test_wsearch_rejects_wrong_host(self):
        with pytest.raises(ValueError, match="not in allowed set"):
            validate_host(
                "https://connect.medlineplus.gov/ws/query",
                ALLOWED_HOSTS_WSEARCH,
                "MedlinePlus",
            )



    def test_ctgov_allows_correct_host(self):
        validate_host(
            "https://clinicaltrials.gov/api/v2/studies/NCT04057716",
            ALLOWED_HOSTS_CTGOV,
            "ClinicalTrials.gov",
        )

    def test_ctgov_rejects_wrong_host(self):
        with pytest.raises(ValueError, match="not in allowed set"):
            validate_host(
                "https://evil.example.com/api/v2/studies",
                ALLOWED_HOSTS_CTGOV,
                "ClinicalTrials.gov",
            )
    def test_allowlist_rejects_none_host(self):
        """A relative URL or garbage string should not pass."""
        with pytest.raises(ValueError, match="not in allowed set"):
            validate_host(
                "/some/relative/path",
                ALLOWED_HOSTS_REPORTER,
                "RePORTER",
            )


# ── Input-size guard tests ──────────────────────────────────────────────────


class TestInputSizeGuards:
    """Every free-text string param must be capped; oversized inputs rejected."""

    def test_validate_topic_accepts_normal(self):
        assert validate_topic("CRISPR gene editing") == "CRISPR gene editing"

    def test_validate_topic_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            validate_topic("")

    def test_validate_topic_rejects_oversized(self):
        with pytest.raises(ValueError, match="too long"):
            validate_topic("x" * (MAX_STRING_LEN + 1))

    def test_validate_topic_at_exact_limit(self):
        """Exactly MAX_STRING_LEN chars should be accepted."""
        result = validate_topic("x" * MAX_STRING_LEN)
        assert len(result) == MAX_STRING_LEN

    def test_validate_string_length_accepts_normal(self):
        assert validate_string_length("Smith", "last_name") == "Smith"

    def test_validate_string_length_rejects_oversized(self):
        with pytest.raises(ValueError, match="too long"):
            validate_string_length("x" * 501, "last_name")

    def test_validate_string_length_strips_whitespace(self):
        assert validate_string_length("  Smith  ", "last_name") == "Smith"

    def test_validate_string_length_custom_cap(self):
        """A custom max_len (e.g. 15000 for research_text) is respected."""
        validate_string_length("x" * 15000, "research_text", max_len=15000)
        with pytest.raises(ValueError, match="too long"):
            validate_string_length("x" * 15001, "research_text", max_len=15000)

    def test_validate_list_length_accepts_normal(self):
        assert validate_list_length(["NCI", "NIMH"], "agencies") == ["NCI", "NIMH"]

    def test_validate_list_length_rejects_oversized(self):
        with pytest.raises(ValueError, match="Too many"):
            validate_list_length(list(range(21)), "agencies")

    def test_validate_fiscal_years_rejects_oversized(self):
        with pytest.raises(ValueError, match="Too many"):
            validate_fiscal_years(list(range(2000, 2025)))


# ── Combined: allowlist constants are correct ───────────────────────────────


class TestAllowlistConstants:
    """Verify the allowlists contain exactly the expected hosts."""

    def test_reporter_hosts(self):
        assert ALLOWED_HOSTS_REPORTER == frozenset({"api.reporter.nih.gov"})

    def test_eutils_hosts(self):
        assert ALLOWED_HOSTS_EUTILS == frozenset({"eutils.ncbi.nlm.nih.gov"})

    def test_ctgov_hosts(self):
        assert ALLOWED_HOSTS_CTGOV == frozenset({"clinicaltrials.gov"})

    def test_wsearch_hosts(self):
        assert ALLOWED_HOSTS_WSEARCH == frozenset({"wsearch.nlm.nih.gov"})
