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
    abstract: str | None = Field(
        None,
        description="Project abstract (populated for detail lookups via get_project_by_id, None for search results).",
    )
    start_date: str | None = Field(
        None, description="Project start date, ISO format (detail lookups only)."
    )
    end_date: str | None = Field(
        None, description="Project end date, ISO format (detail lookups only)."
    )
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
    orphan_child_count: int = 0


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


# ── Clinical Trials Linkage ─────────────────────────────────────────────────

EVIDENCE_CLASS_SOURCE_ASSERTED = "source_asserted"
EVIDENCE_CLASS_CANDIDATE = "candidate"

GRANT_TRIAL_BOUNDARY_NOTE = (
    "A grant↔trial link indicates the trial record references the grant. "
    "It does NOT establish that the grant caused a trial outcome, does NOT "
    "identify which fiscal year's funding supported the trial, and a missing "
    "link does NOT establish that no relationship exists. Registrants control "
    "which grant IDs appear in a trial record; omissions and errors are common."
)

DOLLAR_ATTRIBUTION_NOTE = (
    "No dollar figures are attributed to linked trials. A single NIH award "
    "may fund multiple trials, and a single trial may cite multiple awards. "
    "Multiplying grant funding across linked trials would double-count."
)


class TrialDatePair(BaseModel):
    """Preserves the ClinicalTrials.gov distinction between estimated and actual."""
    estimated: str | None = Field(None, description="Estimated date (from the registered plan).")
    actual: str | None = Field(None, description="Actual date (from results reporting).")


class LinkedGrant(BaseModel):
    """A grant ID found in a trial record, with its evidence class."""
    grant_id: str = Field(..., description="The grant identifier as registered in the trial record.")
    id_type: str = Field(
        ..., description="ClinicalTrials.gov secondaryIdInfo type: 'NIH', 'OTHER_GRANT', 'OTHER', 'REGISTRY', 'EUDRACT_NUMBER'."
    )
    id_source: str = Field(
        ..., description="Where the ID appeared: 'secondaryIdInfos' or 'orgStudyIdInfo'."
    )
    is_nih: bool = Field(..., description="True if type=='NIH'. The only reliable NIH discriminator.")
    domain: str | None = Field(
        None, description="Funder domain (for non-NIH grants, e.g. 'Food and Drug Administration')."
    )
    reporter_link: str | None = Field(
        None, description="Link to NIH RePORTER quick search (present only for type=='NIH')."
    )


class LinkedTrial(BaseModel):
    """A clinical trial linked to one or more NIH grants."""
    nct_id: str
    brief_title: str | None = None
    overall_status: str | None = None
    study_type: str | None = Field(
        None, description="'INTERVENTIONAL' or 'OBSERVATIONAL' (from designModule.studyType)."
    )
    phases: list[str] = Field(default_factory=list)
    lead_sponsor: str | None = None
    lead_sponsor_class: str | None = Field(
        None, description="Sponsor class: 'NIH', 'FED', 'OTHER', 'INDUSTRY', etc."
    )
    nih_collaborators: list[str] = Field(
        default_factory=list,
        description="NIH institute/center collaborators (class=='NIH').",
    )
    start_date: TrialDatePair = Field(default_factory=TrialDatePair)
    completion_date: TrialDatePair = Field(default_factory=TrialDatePair)
    enrollment: int | None = Field(None, description="Target or actual enrollment count.")
    enrollment_type: str | None = Field(None, description="'ESTIMATED' or 'ACTUAL'.")
    linked_grants: list[LinkedGrant] = Field(
        default_factory=list,
        description="All grant IDs found in this trial record (NIH and non-NIH).",
    )
    nih_grant_ids: list[str] = Field(
        default_factory=list,
        description="Subset: only grant IDs with type=='NIH'.",
    )
    evidence_class: str = Field(
        EVIDENCE_CLASS_SOURCE_ASSERTED,
        description=(
            "'source_asserted' when the trial record structurally declares "
            "the NIH grant via type='NIH'; 'candidate' when the link is "
            "inferred (e.g. condition search, text match without type field)."
        ),
    )
    clinicaltrials_url: str | None = None


class ClinicalTrialsResult(BaseModel):
    """Result of clinical_trials_lookup."""
    query_type: str = Field(
        ..., description="'grant' or 'condition' — how the lookup was performed."
    )
    query_value: str = Field(..., description="The grant ID or condition searched.")
    grant_id_variants_tried: list[str] = Field(
        default_factory=list,
        description="For grant lookups: all project_num variants tried against CT.gov.",
    )
    distinct_trials: int = Field(
        ..., description="Count of distinct NCT IDs found."
    )
    distinct_relationships: int = Field(
        ..., description="Count of distinct (core_project_num, nct_id) pairs."
    )
    trials: list[LinkedTrial]
    boundary_note: str = GRANT_TRIAL_BOUNDARY_NOTE
    dollar_attribution_note: str = DOLLAR_ATTRIBUTION_NOTE
    source_api: str = "https://clinicaltrials.gov/api/v2"
    retrieved_at: str = Field(..., description="UTC ISO timestamp.")
