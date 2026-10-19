"""Resource: response formatting guidelines for the LLM agent."""

from __future__ import annotations

import json

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.resource(
        "nih-reporter://response-guidelines",
        name="response_guidelines",
        description=(
            "Formatting rules for presenting funding data to users. "
            "MUST be consulted before answering any 'how many' or 'how much' question."
        ),
    )
    def response_guidelines() -> str:
        return json.dumps(
            {
                "lead_with_one_number": {
                    "rule": (
                        "Every 'how many' or 'how much' question must be answered with "
                        "ONE number in the first sentence, followed by its basis. "
                        "Example: 'Based on keyword search, 561 projects mention HuBMAP across all fiscal years.' "
                        "Then offer alternatives: 'If you meant parent awards only (excluding subprojects): 332.'"
                    ),
                    "anti_pattern": (
                        "Do NOT lead with multiple competing numbers. "
                        "Do NOT present dollar totals as if they answer a count question. "
                        "Do NOT bury the load-bearing caveat (keyword vs program, approximate vs exact) "
                        "in a footnote or trailing paragraph."
                    ),
                },
                "keyword_vs_program": {
                    "rule": (
                        "When the user asks about a PROGRAM (e.g. 'HuBMAP', 'SPARC', 'All of Us'), "
                        "the keyword-based count is an approximation, not a program roster. "
                        "State this in the headline: 'Based on keyword search (not a program-level filter), ...' "
                        "RePORTER does not expose a Common Fund or program-membership filter."
                    ),
                },
                "subproject_alternatives": {
                    "rule": (
                        "When reporting counts, label what question each number answers: "
                        "'X parent awards (distinct funded projects, excluding sub-components)' vs "
                        "'Y total records (including subprojects of multi-component grants)'. "
                        "The parent-award count is the default answer for 'how many awards'."
                    ),
                },
                "methodology_caveats": {
                    "rule": (
                        "For RCDC categories, state whether the total matches or diverges from "
                        "the published figure, and by how much. For free-text search, note that "
                        "it includes every project MENTIONING the term, not just projects where "
                        "the topic is the primary focus."
                    ),
                },
            },
            indent=2,
        )
