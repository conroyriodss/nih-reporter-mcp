# NIH RePORTER MCP Server

An MCP (Model Context Protocol) server that gives AI agents goal-oriented access to live NIH grant funding data via [NIH RePORTER](https://reporter.nih.gov/), the authoritative public record of NIH and other HHS-agency research funding (~$42B/year across NIH, CDC, FDA, and ACF).

Built for the [GSA MCP Server and AI Agent Government Hackathon](https://www.gsa.gov/artificial-intelligence/ai-community-of-practice/events-and-training/mcp-server-and-ai-agent-government-hackathon).

## Why this exists

Two distinct government use cases, one server:

- **Oversight**: "How much has NIH spent on X?" "Is funding for Y growing or shrinking?" "What's NIH's official spending category say vs. what a keyword search finds?" — answerable by program staff, Congress, or the public without manually querying raw APIs.
- **Service delivery / research discovery**: "What's funded in this area?" "What came out of this grant?" "What's this investigator's portfolio?" — answerable by researchers, clinicians, or journalists.

Rather than wrapping RePORTER's raw REST endpoints 1:1, every tool here is designed around a **user goal**, with validated inputs, structured outputs, and honest reporting of the API's real limitations (a 10,000-record hard ceiling, ambiguous organization name matching, free-text search vs. official categorization) — because those limitations produce wrong answers if hidden, and useful ones if surfaced.

## Tools

| Tool | Purpose |
|---|---|
| `search_funded_projects` | Find funded projects matching a topic, with filters (fiscal year, state, agency, active/inactive) |
| `summarize_funding_by_topic` | Exact total NIH/HHS investment in a topic, via full pagination (not a 500-record estimate). Accepts either free-text or an official NIH spending category |
| `funding_trend_by_year` | Year-by-year funding trend for a topic or spending category |
| `organization_funding_profile` | Funding profile for a named institution, with exact-name matching by default to avoid silently combining similarly-named institutions |
| `investigator_portfolio` | Funded portfolio for a named researcher |
| `get_project_by_id` | Direct lookup by application ID or core project number |
| `list_publications_for_project` | PubMed IDs linked to a project |
| `get_publication_details` | Resolves PubMed IDs into full citations (title, journal, authors) via NCBI E-utilities — closes the gap left by RePORTER's publications endpoint, which returns bare IDs only |

See [`docs/findings.md`](docs/findings.md) for documented data-quality discoveries made during development (several are directly relevant to anyone else building on this API) and [`docs/roadmap.md`](docs/roadmap.md) for planned future tools.

## Quickstart

```bash
git clone <this-repo>
cd nih-reporter-mcp
uv sync
uv run python main.py
```

Server starts on stdio by default (for local MCP client testing, e.g. Claude Desktop or MCP Inspector). Set `PORT` or `DATABRICKS_APP_PORT` to serve Streamable HTTP instead. For Databricks Apps deployment, see [`deploy/databricks/app.yaml`](deploy/databricks/app.yaml).

No API key or authentication is required for the underlying NIH RePORTER or NCBI E-utilities APIs.

## Evaluation

9 automated assertions against live RePORTER data (not mocked), covering exact-total correctness, the 10,000-record ceiling, organization-name disambiguation, a documented RCDC-category-vs-free-text divergence, input validation, and injection-style input handling. Also includes a measured, reproducible LLM agent-efficiency improvement (tool-call count per question: 2.0 avg / stdev 1.7 → 1.0 avg / stdev 0.0, attributable to a single tool-description clarification, model held constant). See [`eval/README.md`](eval/README.md) for how to run the suite and [`docs/findings.md`](docs/findings.md) for the full writeup of what was found and fixed.

```bash
uv run python main.py &
sleep 5
uv run python eval/smoke_tests.py   # t1–t8 standalone; t9 requires notebook
```

The full 9-test suite (including t9, the LLM agent-efficiency regression guard) runs inside the companion Databricks notebook (`notebook-merged`).

## Known limitations

- No query can return more than 10,000 matching records (an upstream RePORTER API ceiling); tools report this via a `complete` flag rather than silently truncating.
- Organization name matching is substring-based by default upstream; `organization_funding_profile` defaults to exact-name matching to avoid combining similarly-named institutions, with guidance to discover the correct exact name if needed.
- `summarize_funding_by_topic`'s curated spending-category lookup covers ~38 commonly-queried NIH RCDC categories out of ~300 total; others require the numeric category ID (see NIH RePORTER API Data Elements, Appendix I).
- `investigator_portfolio` matches on name text, not a stable person ID; common surnames require a first name to disambiguate.
- Two tools are stubbed but not implemented: ClinicalTrials.gov cross-linking and USAspending.gov cross-agency comparison. See [`docs/roadmap.md`](docs/roadmap.md).

## License

MIT. See [`SECURITY.md`](SECURITY.md) for the vulnerability disclosure policy.
