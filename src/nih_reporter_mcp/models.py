"""Pydantic models for tool parameters and return types."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    complete: bool = Field(..., description="True if every matching project was included in the totals.")
    total_award_amount_usd: float
    distinct_organizations: int
    distinct_administering_ics: int
    pages_fetched: int
    note: str


class YearFunding(BaseModel):
    fiscal_year: int
    project_count: int
    total_award_amount_usd: float
    complete: bool


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
    top_administering_ics: list[str]
    sample_projects: list[ProjectSummary]
    note: str


class InvestigatorPortfolio(BaseModel):
    investigator_query: str
    fiscal_years: list[int] | None
    total_matching_projects: int
    returned: int
    truncated: bool
    total_award_amount_usd_returned: float
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
