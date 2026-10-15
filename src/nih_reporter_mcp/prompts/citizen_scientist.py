"""Prompts for citizen scientists and non-expert audiences.

Two prompts that use the same underlying tools as the analyst/program-officer
prompts but instruct the agent to write for a lay reader: define jargon,
clarify institutional geography, distinguish planned from reported research,
and avoid technical density.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="explain_funding_landscape",
        description=(
            "Plain-language funding landscape for a non-expert reader. "
            "Uses the same tools as research_landscape_summary but instructs "
            "the agent to define jargon, clarify institutional geography, "
            "and include the NIH-only scope disclaimer in accessible terms."
        ),
    )
    def explain_funding_landscape(topic: str) -> str:
        current_fy = 2026
        start_fy = current_fy - 4  # 5-year window
        fy_list = list(range(start_fy, current_fy + 1))
        fy_str = ", ".join(str(y) for y in fy_list)

        return (
            f"Write a plain-language overview of how the US government "
            f'funds research on "{topic}" for a non-expert reader. '
            f"Follow these steps:\n\n"
            f"1. Call **summarize_funding_by_topic** with "
            f'   topic="{topic}" and fiscal_years=[{fy_str}] to get '
            f"   the total investment and project count.\n"
            f"2. Call **funding_trend_by_year** with "
            f'   topic="{topic}", start_year={start_fy}, '
            f"   end_year={current_fy} to show how funding has changed "
            f"   over time.\n"
            f"3. Call **search_funded_projects** with "
            f'   topic="{topic}", fiscal_years=[{current_fy}], '
            f"   sort_by_award=true, limit=10 to find the largest "
            f"   currently-funded efforts.\n\n"
            f"Write the results for a general audience:\n\n"
            f"- **Define jargon**: when you mention terms like R01, U01, "
            f"  IC, PI, mechanism, or RCDC, briefly explain what they mean "
            f"  in parentheses.\n"
            f"- **Clarify geography**: the organization listed for a grant "
            f"  is the recipient institution (where the money goes), not "
            f"  necessarily where the research is physically conducted. "
            f"  State this explicitly.\n"
            f"- **Planned vs reported**: distinguish between what a grant "
            f"  proposes to study (the funded aims) and what has actually "
            f"  been discovered or published. Grant titles and abstracts "
            f"  describe planned research, not confirmed findings.\n"
            f"- **Avoid technical density**: use short sentences, round "
            f"  dollar figures to millions/billions, and lead with the "
            f"  'so what' before the numbers.\n\n"
            f"**NIH-ONLY SCOPE DISCLAIMER** (include in your response, "
            f"in plain language):\n"
            f"This overview covers only grants funded by the National "
            f"Institutes of Health (NIH), which is one part of the US "
            f"Department of Health and Human Services. Other government "
            f"agencies (NSF, DOD, VA), private companies, universities, "
            f"and international organisations also fund research on this "
            f"topic -- their spending is not included here."
        )

    @mcp.prompt(
        name="follow_the_evidence",
        description=(
            "Lay-reader version of investment_to_outputs: narrates the "
            "research question, what was studied, and what was published, "
            "in plain language. Distinguishes planned research from "
            "reported findings."
        ),
    )
    def follow_the_evidence(core_project_num: str) -> str:
        return (
            f"Tell the story of NIH-funded project {core_project_num} for "
            f"a non-expert reader.\n\n"
            f"1. Call **get_project_by_id** with "
            f'   project_num="{core_project_num}" to get the project '
            f"   details.\n"
            f"2. Call **list_publications_for_project** with "
            f'   core_project_num="{core_project_num}" to find published '
            f"   papers linked to this project.\n"
            f"3. For the first 5 publications returned, call "
            f"   **get_publication_details** with each PMID to get "
            f"   details.\n\n"
            f"Write up the results as a narrative for a general reader:\n\n"
            f"- **The research question**: what is this project trying to "
            f"  answer? Translate the abstract into everyday language.\n"
            f"- **Who and where**: name the lead researcher(s) and their "
            f"  institution. Clarify that the institution is where the "
            f"  grant money goes, not necessarily the only place the work "
            f"  happens.\n"
            f"- **What has been published**: for each paper, summarise the "
            f"  finding in one sentence a non-scientist could understand. "
            f"  If the abstract is too technical, say so honestly rather "
            f"  than guessing.\n"
            f"- **Planned vs actual**: clearly distinguish between what "
            f"  the grant proposed to study (the aims) and what the "
            f"  publications actually report finding.\n"
            f"- **What we don't know**: note that linked publications are "
            f"  reported by the researchers or publishers -- the link does "
            f"  not guarantee the paper was funded by this specific grant, "
            f"  and not every result from the project may be published yet."
        )
