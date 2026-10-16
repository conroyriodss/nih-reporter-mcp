"""Prompts for NIH program officers.

Three prompts that compose existing tools into workflows tailored for
program-officer tasks: portfolio briefs with reproducible provenance,
public funded-award screening for overlap candidates, and
investment-to-outputs dossiers.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="portfolio_brief",
        description=(
            "Reproducible cohort brief for a research topic, broken down by "
            "IC and mechanism. Calls summarize_funding_by_topic (both "
            "free-text AND spending_category where one exists), then "
            "export_evidence_bundle, and presents the counting-unit caveat "
            "and source record IDs for full auditability."
        ),
    )
    def portfolio_brief(topic: str, fiscal_years_csv: str = "2024") -> str:
        fy_list = [y.strip() for y in fiscal_years_csv.split(",")]
        fy_param = ", ".join(fy_list)
        return (
            f"Produce a reproducible portfolio brief for \"{topic}\" in "
            f"FY {fy_param}. Follow these steps:\n\n"
            f"1. Call **summarize_funding_by_topic** with "
            f'   topic="{topic}" and fiscal_years=[{fy_param}] to get the '
            f"   free-text search total.\n"
            f"2. Call **summarize_funding_by_topic** with "
            f'   spending_category="{topic}" and fiscal_years=[{fy_param}] '
            f"   to get the live RCDC-category aggregation. Three outcomes "
            f"   are possible: (a) a dollar figure is returned — use it; "
            f"   (b) the total is zero — a matching RCDC category exists "
            f"   but has no projects in this fiscal year; (c) an error is "
            f"   returned — the API call failed, so note the error and "
            f"   continue with the free-text figure only. Do NOT conflate "
            f"   zero results with 'no RCDC category exists'.\n"
            f"3. Call **export_evidence_bundle** with "
            f'   topic="{topic}", fiscal_years=[{fy_param}], and '
            f'   label="{topic} FY{fy_list[0]} portfolio brief" to get the '
            f"   full provenance and source record IDs.\n\n"
            f"Present the results as a cohort brief with:\n"
            f"- **Framing comparison**: free-text total vs live RCDC-category "
            f"  aggregation (if available), with a note on why they differ "
            f"  (live aggregation may not match NIH's frozen published "
            f"  annual totals; categories overlap and are not additive).\n"
            f"- **Breakdown by IC**: top administering Institutes/Centers "
            f"  by distinct project count (dollar breakdowns by IC are not "
            f"  available from the funding summary).\n"
            f"- **Breakdown by mechanism**: R01 vs U01 vs P01 etc. "
            f"  distribution by count (inferred from project numbers in "
            f"  the search results; dollar amounts per mechanism are not "
            f"  directly available).\n"
            f"- **Counting-unit caveat**: state explicitly that the "
            f"  counting_unit is award records where parent and subproject "
            f"  records are counted separately -- this is NOT a deduplicated "
            f"  core-project count, and parent-award totals already include "
            f"  their subprojects' funding. Do not sum across levels.\n"
            f"- **Evidence bundle**: attach the source_record_ids from the "
            f"  evidence bundle so a reviewer can spot-check individual "
            f"  appl_ids against RePORTER."
        )

    @mcp.prompt(
        name="other_support_review",
        description=(
            "Screen an investigator's publicly funded NIH awards for "
            "candidate overlap as input to Other Support review. Calls "
            "check_investigator_overlap and presents results with an "
            "explicit boundary statement that this is a public-record "
            "screening tool, not a complete duplication determination "
            "(pending, non-NIH, and unpublished support are not visible)."
        ),
    )
    def other_support_review(
        last_name: str,
        first_name: str,
        exclude_project_num: str = "",
    ) -> str:
        excl = ""
        if exclude_project_num:
            excl = (
                f'   Also pass exclude_project_num="{exclude_project_num}" '
                f"   to remove the project under review from the results.\n"
            )
        return (
            f"Screen publicly funded NIH awards for {first_name} "
            f"{last_name} for candidate overlap as input to Other Support "
            f"review.\n\n"
            f"1. Call **check_investigator_overlap** with "
            f'   last_name="{last_name}", first_name="{first_name}".\n'
            f"{excl}\n"
            f"Present the results as:\n"
            f"- **Active awards list**: project number, title, role, "
            f"  organization, total award amount.\n"
            f"- **Flagged awards**: any awards flagged by the overlap "
            f"  detection heuristics, with the reason for each flag.\n\n"
            f"**BOUNDARY STATEMENT** (include verbatim in your response):\n"
            f"\"This surfaces candidate overlapping support for a human "
            f"reviewer; it does not determine actual scientific or "
            f"budgetary duplication. Verify aims, dates, and direct costs "
            f"manually.\""
        )

    @mcp.prompt(
        name="investment_to_outputs",
        description=(
            "Dossier of documented outputs for a specific project: project "
            "details (including abstract and funding period), linked "
            "publications, and publication metadata (title, journal, "
            "authors, DOI). Calls get_project_by_id, "
            "list_publications_for_project, and get_publication_details "
            "in sequence."
        ),
    )
    def investment_to_outputs(core_project_num: str) -> str:
        return (
            f"Produce an investment-to-outputs dossier for project "
            f"{core_project_num}.\n\n"
            f"1. Call **get_project_by_id** with "
            f'   core_project_num="{core_project_num}" to get the project '
            f"   details (title, abstract, PI, organization, funding "
            f"   period, award amount).\n"
            f"2. Call **list_publications_for_project** with "
            f'   core_project_num="{core_project_num}" to get linked '
            f"   publications.\n"
            f"3. For the first 5 publications returned, call "
            f"   **get_publication_details** with each PMID to get title, "
            f"   journal, authors, date, and DOI.\n\n"
            f"Present the results as a dossier:\n"
            f"- **Project overview**: title, PI, organization, abstract, "
            f"  funding period (start_date to end_date), award amount.\n"
            f"- **Publications table**: PMID, title, journal, year, DOI.\n"
            f"- **Publication-funding link**: label each grant-paper "
            f"  association as 'source_reported' (reported by the PI or "
            f"  publisher to NIH).\n\n"
            f"**IMPORTANT**: do NOT attribute publications to specific "
            f"funding years. NIH's own FAQ states that publication "
            f"associations cannot identify a funding year -- the link is "
            f"between the publication and the core project number, not a "
            f"specific fiscal year's award."
        )
