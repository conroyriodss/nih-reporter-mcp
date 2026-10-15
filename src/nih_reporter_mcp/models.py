"""Pydantic models for tool parameters and return types."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Provenance ──────────────────────────────────────────────────────────────

COUNTING_UNIT_WHOLE = (
    "funding_basis=whole_award: subproject records excluded, appl_ids "
    "deduplicated, missing amounts excluded (not zeroed). This total counts "
    "each parent award once."
)
COUNTING_UNIT_ALL = (
    "funding_basis=all_records: every record (parent + subproject) is summed; "
    "appl_ids are still deduplicated and missing amounts are excluded. "
    "Parent-award totals already include their subprojects' funding, so this "
    "total double-counts multi-project grants. Use whole_award for investment "
    "figures."
)
# Legacy alias for backward compat in EvidenceBundle etc.
COUNTING_UNIT = COUNTING_UNIT_WHOLE


class Provenance(BaseModel):
    retrieved_at: str = Field(
        ..., description="UTC ISO timestamp when the upstream data was retrieved."
    )
    query_criteria: dict = Field(
        ..., description="The exact criteria object sent to the RePORTER API."
    )
    total_matching: int = Field(
        ..., description="Total records the API reported as matching."
    )
    records_aggregated: int = Field(
        ..., description="Records that contributed a dollar amount to the total (post-dedup, post-filtering, non-null award_amount). Equals len(source_record_ids) when the list is not capped."
    )
    complete: bool = Field(
        ..., description="True if every matching record was fetched from the API."
    )
    pages_fetched: int
    deduped_count: int = Field(
        0, description="Records skipped as appl_id duplicates (e.g. page-boundary repeats)."
    )
    subproject_excluded_count: int = Field(
        0, description="Subproject records excluded in whole_award mode."
    )
    records_with_missing_amount: int = Field(
        0, description="Records with no award_amount on file (excluded from total, not zeroed)."
    )
    funding_basis: str = Field(
        "whole_award", description="'whole_award' or 'all_records'."
    )
    source_api: str = "https://api.reporter.nih.gov/v2/projects/search"
    source_record_ids: list[int] = Field(
        default_factory=list,
        description=(
            "appl_ids of the records that contributed to the dollar total "
            "(post-dedup, post-subproject-exclusion, non-null amount). "
            "Capped at 500; see records_aggregated for the true count."
        ),
    )
    id_conflicts: list[int] = Field(
        default_factory=list,
        description=(
            "appl_ids that appeared multiple times with conflicting "
            "award_amount, fiscal_year, or subproject_id. First occurrence "
            "was counted; subsequent deduped. Investigate manually if present."
        ),
    )


class ProjectSummary(BaseModel):
    core_project_num: str | None = Field(None, description="Core project number, e.g. 'R01AG012345'.")
    title: str | None = Field(None, description="Funded project title.")
    award_amount: float | None = Field(None, description="Award amount in USD for the fiscal year (NIH/CDC/FDA/ACF only).")
    fiscal_year: int | None = None
    organization: str | None = Field(None, description="Recipient organization name.")
    org_state: str | None = None
    principal_investigators: list[str] = Field(default_factory=list)
    administering_ic: str | None = Field(None, description="Administering NIH Institute/Center or agency abbreviation.")
    reporter_url: str | None = Field(None, description="Link to the full project record on RePORTER.")


class SearchResult(BaseModel):
    total_matching_projects: int
    returned: int
    truncated: bool = Field(..., description="True if more matches exist than were returned.")
    projects: list[ProjectSummary]


class FundingSummary(BaseModel):
    topic: str
    fiscal_years: list[int] | None
    total_matching_projects: int
    projects_aggregated: int
    complete: bool = Field(..., description="True if every matching project was fetched from the API.")
    total_award_amount_usd: float
    funding_basis: str = Field("whole_award", description="'whole_award' or 'all_records'.")
    records_with_missing_amount: int = Field(
        0, description="Records with no award_amount (excluded from total, not zeroed)."
    )
    deduped_count: int = Field(0, description="Records skipped as appl_id duplicates.")
    subproject_excluded_count: int = Field(0, description="Subproject records excluded.")
    distinct_organizations: int
    distinct_administering_ics: int
    pages_fetched: int
    counting_unit: str = COUNTING_UNIT
    provenance: Provenance | None = Field(
        None, description="Full audit trail. Present when include_provenance=True."
    )
    note: str


class YearFunding(BaseModel):
    fiscal_year: int
    project_count: int
    total_award_amount_usd: float
    complete: bool
    records_with_missing_amount: int = 0


class FundingTrend(BaseModel):
    topic: str
    years: list[YearFunding]
    note: str


class OrgProfile(BaseModel):
    organization_query: str
    matched_org_names: list[str]
    fiscal_years: list[int] | None
    total_matching_projects: int
    projects_aggregated: int
    complete: bool
    total_award_amount_usd: float
    funding_basis: str = Field("whole_award", description="'whole_award' or 'all_records'.")
    records_with_missing_amount: int = 0
    deduped_count: int = 0
    subproject_excluded_count: int = 0
    top_administering_ics: list[str]
    sample_projects: list[ProjectSummary]
    counting_unit: str = COUNTING_UNIT
    provenance: Provenance | None = Field(
        None, description="Full audit trail. Present when include_provenance=True."
    )
    note: str


class InvestigatorPortfolio(BaseModel):
    investigator_query: str
    fiscal_years: list[int] | None
    total_matching_projects: int
    returned: int
    truncated: bool
    total_award_amount_usd_returned: float
    records_with_missing_amount: int = Field(
        0, description="Records with no award_amount (excluded from total, not zeroed)."
    )
    subproject_excluded_count: int = Field(
        0, description="Subproject records excluded from the dollar total."
    )
    projects: list[ProjectSummary]
    note: str


class Publication(BaseModel):
    pmid: int
    core_project_num: str | None
    appl_id: int | None
    pubmed_url: str


class PublicationList(BaseModel):
    core_project_num: str
    total_publications: int
    returned: int
    truncated: bool
    publications: list[Publication]
    note: str
