# Security

## Reporting a vulnerability

Open a GitHub issue or contact the maintainer listed in the repository. This is a hackathon prototype, not a production service; please disclose responsibly and allow reasonable time to respond before public disclosure.

## Data handling

- No authentication, API keys, or secrets are required or stored. Both upstream APIs (NIH RePORTER, NCBI E-utilities) are public, unauthenticated, read-only data sources.
- No user data is collected, logged, or persisted by this server. All requests are pass-through queries against public government datasets.
- No PII is processed. NIH RePORTER data includes investigator names, which are already public record as part of federal grant award disclosure.

## Network hardening

Both upstream HTTP clients (`utils.py` for RePORTER, `tools/publication_details.py` for E-utilities) are hardened against request-forgery and resource-exhaustion risks even though upstream hosts are fixed and never user-controllable:

- `follow_redirects=False` on every outbound request — prevents a compromised or misconfigured upstream from silently redirecting requests elsewhere.
- `trust_env=False` — prevents environment-variable-based proxy injection from rerouting traffic.
- Response size bounded before JSON parsing, to prevent memory exhaustion from an anomalously large response.
- All outbound hosts are hardcoded constants (`api.reporter.nih.gov`, `eutils.ncbi.nlm.nih.gov`); no user input is ever used to construct a request URL or host.

## Input validation

Every tool validates its inputs before making any network call (empty/whitespace strings, malformed state codes, implausible fiscal years, oversized date ranges, oversized list parameters) and returns a clear, specific error rather than passing unvalidated input upstream. This was tested directly against SQL-injection-style input strings; the upstream API's own WAF returns a 403 in that case, which this server surfaces as a clean, actionable error rather than a leaked stack trace (see `docs/findings.md`).

## Rate limiting

Both upstream clients implement courtesy rate limiting (RePORTER: ~1 req/sec; E-utilities: ~3 req/sec without an API key) via an internal async lock, to avoid overwhelming either public API regardless of how many concurrent tool calls an agent issues.

## Dependencies

Dependency versions are pinned in `pyproject.toml`. No dependency requires network access beyond the two documented upstream APIs.
