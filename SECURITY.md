# Security

## Reporting a vulnerability

Open a GitHub issue or contact the maintainer listed in the repository. This is a hackathon prototype, not a production service; please disclose responsibly and allow reasonable time to respond before public disclosure.

## Data handling

- No authentication, API keys, or secrets are required or stored. All three upstream APIs (NIH RePORTER, NCBI E-utilities, MedlinePlus/NLM Web Search) are public, unauthenticated, read-only data sources.
- No user data is collected, logged, or persisted by this server. All requests are pass-through queries against public government datasets.
- No PII is processed. NIH RePORTER data includes investigator names, which are already public record as part of federal grant award disclosure.

## Fixed upstream origins (3)

This server contacts exactly three hosts, all hardcoded:

| Client | File | Host | Protocol |
|---|---|---|---|
| RePORTER projects/publications | `utils.py` | `api.reporter.nih.gov` | HTTPS POST |
| NCBI E-utilities (PubMed) | `tools/publication_details.py` | `eutils.ncbi.nlm.nih.gov` | HTTPS GET |
| MedlinePlus Web Search | `tools/explain_health_topic.py` | `wsearch.nlm.nih.gov` | HTTPS GET |

No user input is ever used to construct a URL or host.

## Per-client host allowlists

Every HTTP client validates the target URL's hostname against a per-client allowlist **before** making any network call (`validate_host()` in `utils.py`). Three frozen sets:

- `ALLOWED_HOSTS_REPORTER = {"api.reporter.nih.gov"}`
- `ALLOWED_HOSTS_EUTILS = {"eutils.ncbi.nlm.nih.gov"}`
- `ALLOWED_HOSTS_WSEARCH = {"wsearch.nlm.nih.gov"}`

A request to any other host raises `ValueError` immediately. This is defense-in-depth: the URLs are also hardcoded constants, so a disallowed host would require a code change — but the allowlist catches configuration drift, accidental refactors, or a compromised dependency that attempts to redirect a URL.

Unit-tested in `tests/test_security.py`.

## Five per-request protections

All three HTTP clients enforce all five protections on every outbound request:

| Protection | Purpose | RePORTER | E-utilities | MedlinePlus |
|---|---|:---:|:---:|:---:|
| `follow_redirects=False` | Block open-redirect abuse | ✅ | ✅ | ✅ |
| `trust_env=False` | Block env-var proxy injection | ✅ | ✅ | ✅ |
| Timeout | Bound latency | 30s | 15s | 15s |
| Response-size cap | Prevent memory exhaustion | 10 MB | 10 MB | 5 MB |
| Rate limiter | Prevent upstream abuse | 1 req/s | 3 req/s | 2 req/s |

## Input validation

**String-length caps:** Every free-text string parameter is capped before it reaches any network call:

| Parameter | Cap | Enforced by |
|---|---:|---|
| `topic` (RePORTER tools) | 500 chars | `validate_topic()` |
| `topic` (MedlinePlus) | 500 chars | inline in `explain_health_topic` |
| `organization_name` | 500 chars | `validate_topic()` (reused) |
| `last_name` | 500 chars | `validate_topic()` (reused) |
| `first_name` | 500 chars | `validate_string_length()` |
| `core_project_num` | 500 chars | `validate_string_length()` or `validate_topic()` |
| `exclude_project_num` | 500 chars | `validate_string_length()` |
| `label` | 500 chars | `validate_string_length()` |

**List-length caps:** Every list parameter is bounded:

| Parameter | Cap | Enforced by |
|---|---:|---|
| `fiscal_years` | 20 items | `validate_fiscal_years()` |
| `agencies` / `org_names` | 20 items | `validate_list_length()` |
| `pmids` | 200 items | inline in `get_publication_details` |

**Other:** State codes validated to exactly 2 alpha characters. Spending categories resolved through a curated lookup (not passed raw). Funding\_basis constrained to `"whole_award"` or `"all_records"`. All rejections produce a clear `ValueError`, never a leaked traceback.

SQL-injection-style inputs are handled cleanly: the upstream API's own WAF returns HTTP 403, which this server surfaces as an actionable error (see `docs/findings.md` #6).

Unit-tested in `tests/test_security.py`.

## Rate limiting

All upstream clients implement courtesy rate limiting via an internal async lock, to avoid overwhelming any public API regardless of how many concurrent tool calls an agent issues. Rate limits are per-HTTP-request (not per-tool-call), so `asyncio.gather`-based parallelism in `funding_trend_by_year` still respects the limiter.

## Dependencies

Dependency versions are pinned in `pyproject.toml`. No dependency requires network access beyond the three documented upstream APIs.
