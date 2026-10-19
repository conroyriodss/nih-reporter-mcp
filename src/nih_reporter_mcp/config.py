"""Constants, spending-category lookup, and configuration."""

from __future__ import annotations

import datetime

API_BASE = "https://api.reporter.nih.gov/v2"
PROJECTS_SEARCH = f"{API_BASE}/projects/search"
PUBLICATIONS_SEARCH = f"{API_BASE}/publications/search"
PROJECT_URL = "https://reporter.nih.gov/project-details/{appl_id}"
PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

MIN_REQUEST_INTERVAL = 1.0
REQUEST_TIMEOUT = 30.0
PAGE_SIZE = 500
MAX_PAGES = 20
EARLIEST_FISCAL_YEAR = 1985
LATEST_FISCAL_YEAR = datetime.date.today().year + 1
MAX_OFFSET_PROJECTS = 14999
MAX_OFFSET_PUBLICATIONS = 9999
MAX_RESULT_SET = 10000

SPENDING_CATEGORIES: dict[str, int] = {
    "alzheimer's disease": 40,
    "arthritis": 55,
    "alzheimer's disease including adrd": 3246,
    "cancer": 132,
    "breast cancer": 120,
    "lung cancer": 409,
    "prostate cancer": 703,
    "pancreatic cancer": 1391,
    "pediatric cancer": 2310,
    "hiv/aids": 284,
    "gene therapy": 272,
    "diabetes": 224,
    "obesity": 551,
    "autism": 67,
    "depression": 219,
    "major depressive disorder": 2613,
    "anxiety disorders": 2610,
    "opioid misuse and addiction": 4076,
    "long covid": 5194,
    "post-acute sequelae of sars-cov-2 infection (pasc) including long covid": 5194,
    "coronaviruses": 4835,
    "substance misuse": 817,
    "suicide": 823,
    "suicide prevention": 824,
    "rare diseases": 729,
    "sickle cell disease": 785,
    "stroke": 811,
    "heart disease": 299,
    "chronic pain": 616,
    "traumatic brain injury (tbi)": 375,
    "parkinson's disease": 624,
    "multiple sclerosis": 474,
    "tuberculosis": 864,
    "vaccine related": 877,
    "maternal health": 3810,
    "health disparities research": 5546,
    "machine learning and artificial intelligence": 4372,
    "data science": 4531,
    "precision medicine": 3070,
}


def resolve_spending_category(category: str | int) -> int:
    """Resolve a category name or numeric string to its RCDC integer ID."""
    if isinstance(category, int):
        return category
    if isinstance(category, str) and category.strip().isdigit():
        return int(category.strip())
    key = category.strip().lower()
    if key in SPENDING_CATEGORIES:
        return SPENDING_CATEGORIES[key]
    matches = [name for name in SPENDING_CATEGORIES if key in name or name in key]
    if len(matches) == 1:
        return SPENDING_CATEGORIES[matches[0]]
    if matches:
        raise ValueError(
            f"Ambiguous spending category {category!r}. Did you mean one of: {matches}? "
            "Provide the exact name or the numeric ID."
        )
    raise ValueError(
        f"Unrecognized spending category {category!r}. This tool only has a curated subset "
        f"of NIH's ~300 official categories built in ({len(SPENDING_CATEGORIES)} available). "
        "Provide a numeric RCDC category ID instead if you know it (see NIH RePORTER API "
        "Data Elements Appendix I), or use the topic parameter for a free-text search instead."
    )

# ── ClinicalTrials.gov v2 ───────────────────────────────────────────────────
CTGOV_API_BASE = "https://clinicaltrials.gov/api/v2"
CTGOV_STUDIES = f"{CTGOV_API_BASE}/studies"
CTGOV_STUDY = f"{CTGOV_API_BASE}/studies/{{nct_id}}"
CTGOV_TIMEOUT = 20.0
CTGOV_MIN_REQUEST_INTERVAL = 0.5     # courtesy; no auth required
CTGOV_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
CTGOV_MAX_PAGE_SIZE = 20
