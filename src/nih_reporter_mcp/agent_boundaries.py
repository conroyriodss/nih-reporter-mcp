"""Interpretation boundaries for the Ask agent loop (web_app._run_agent).

Two layers, so a boundary survives the agent rather than living only in docs:

1. ``SYSTEM_MESSAGE`` -- the rules are loaded into the actual system message the
   model receives on every Ask request.
2. ``enforce`` -- after the model's final answer, the boundaries are detected
   from the question and the tool results the loop actually received. Any
   boundary the answer does not already state is added, and an answer to an
   unsupported question is withheld and replaced by a plain decline. This
   layer does not depend on the model following instructions.

The four boundaries match docs/evaluation.md: excluded orphan subprojects,
incomplete retrieval (10,000-record ceiling), keyword cohort vs official RCDC
spending category, and unsupported questions (duration ranking,
trainee/workforce outcomes, government-wide spending comparisons).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SYSTEM_MESSAGE = (
    "You are a research funding analyst with live NIH RePORTER tools. Use tools for all "
    "funding questions and cite concrete numbers. State the following boundaries whenever "
    "they apply; they are part of a correct answer, not optional caveats.\n"
    "1. Excluded orphan subprojects. If a result says excluded subproject(s) had no "
    "corresponding parent record (or orphan_child_count > 0), say how many, and that the "
    "associated award-family investment may be missing from the total. Do not describe the "
    "exclusion as removing double-counting.\n"
    "2. Incomplete retrieval. RePORTER returns at most 10,000 records per query. If a result "
    "has complete=false (or cohort_complete=false), say the figure covers only the retrieved "
    "records and is a lower bound, not a complete total, and suggest narrowing the query.\n"
    "3. Keyword vs RCDC scope. A topic query is a keyword (text-search) cohort, not an official "
    "NIH RCDC spending-category total. Say so whenever you report a figure from a topic query. "
    "Use spending_category for official category figures, and note that live tagged data can "
    "differ from NIH's published point-in-time RCDC tables.\n"
    "4. Unsupported questions. These tools cannot rank grants by duration or project-period "
    "length, report trainee, workforce or career outcomes, or compare NIH with government-wide "
    "or other federal spending (USAspending is not integrated). Decline such questions "
    "plainly, say they are not supported, and offer the closest supported analysis. Never "
    "estimate or invent an answer.\n"
    "Funding amounts exist only for NIH, CDC, FDA and ACF records."
)

# -- unsupported question classes (question text only) ------------------------
UNSUPPORTED = {
    "duration_ranking": (
        re.compile(r"\b(longest|shortest)[- ]running\b|\brun (the )?(longest|shortest)\b"
                   r"|\b(longest|shortest) (duration|project[- ]period)\b"
                   r"|\b(rank|sort|order)\w* (\w+ ){0,3}by (duration|length|project[- ]period)\b", re.I),
        "ranking grants by how long they have run (duration or project-period length)",
    ),
    "workforce_outcomes": (
        re.compile(r"\b(trainee|fellow|postdoc|student|scholar)s?\b.{0,80}\b(career|outcome|after|went on|"
                   r"became|retention|employment|workforce)\b|\b(career|workforce) outcomes?\b", re.I),
        "trainee, workforce or career outcomes",
    ),
    "government_wide_comparison": (
        re.compile(r"\b(share|percent(age)?|fraction|proportion)\b.{0,60}\bfederal\b|\bgovernment[- ]wide\b"
                   r"|\busaspending\b|\ball federal (agencies|spending|funding)\b|\bacross (all )?federal agencies\b",
                   re.I),
        "comparing NIH with government-wide or other federal spending (USAspending is not integrated)",
    ),
}
ALREADY_DECLINED = re.compile(r"not supported|does(n't| not) support|cannot answer|can't answer|unable to answer", re.I)

# -- "already stated" checks for the answer text -------------------------------
STATES_ORPHAN = (re.compile(r"subproject|component (record|project)|orphan", re.I), re.compile(r"parent", re.I))
STATES_INCOMPLETE = (re.compile(r"lower bound|incomplete|not (a )?complete|only [\d,]+ of [\d,]+|"
                                r"10,000[- ]record|retrieval (ceiling|limit)", re.I),)
STATES_KEYWORD = (re.compile(r"keyword|text[- ]search|text match|free[- ]text", re.I),
                  re.compile(r"RCDC|spending[- ]categor|official categor", re.I))

_ORPHAN_NOTE = re.compile(r"(\d[\d,]*) excluded subproject\(s\) (?:had no corresponding parent|across one or more years)")


@dataclass
class Boundary:
    id: str
    caveat: str
    stated: tuple = field(default_factory=tuple)
    added_by_guard: bool = False


def _walk(obj):
    """Yield every dict and string inside a tool payload."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
    elif isinstance(obj, str):
        yield obj


def unsupported_class(question: str) -> str | None:
    for cls, (rx, _) in UNSUPPORTED.items():
        if rx.search(question or ""):
            return cls
    return None


def detect(question: str, tool_results: list[dict]) -> list[Boundary]:
    """Boundaries implied by the question and the tool results the loop received.

    ``tool_results`` items: {"tool": name, "args": dict, "payload": full tool output}.
    """
    found: list[Boundary] = []
    orphans, incomplete, keyword_topics = 0, None, []
    for r in tool_results:
        payload, args = r.get("payload"), r.get("args") or {}
        has_dollars = False
        for node in _walk(payload):
            if isinstance(node, str):
                m = _ORPHAN_NOTE.search(node)
                if m:
                    orphans = max(orphans, int(m.group(1).replace(",", "")))
                continue
            if "total_award_amount_usd" in node:
                has_dollars = True
            if isinstance(node.get("orphan_child_count"), int) and node["orphan_child_count"] > 0:
                orphans = max(orphans, node["orphan_child_count"])
            if node.get("complete") is False or node.get("cohort_complete") is False:
                got = node.get("projects_aggregated", node.get("records_aggregated"))
                tot = node.get("total_matching_projects", node.get("total_matching"))
                if incomplete is None or (got is not None and tot is not None):
                    incomplete = (got, tot)
        if has_dollars and args.get("topic") and not args.get("spending_category"):
            if args["topic"] not in keyword_topics:
                keyword_topics.append(args["topic"])

    if orphans:
        found.append(Boundary("orphan_exclusion", (
            f"Excluded subprojects: {orphans} subproject record(s) matched this query but their parent award "
            "was not in the retrieved cohort, so the whole_award basis excluded them. Associated award-family "
            "investment may be missing from this total; the exclusion is not a double-counting correction."),
            STATES_ORPHAN))
    if incomplete is not None:
        got, tot = incomplete
        span = (f"only {got:,} of {tot:,} matching records were aggregated"
                if isinstance(got, int) and isinstance(tot, int) else "not every matching record was retrieved")
        found.append(Boundary("incomplete_retrieval", (
            f"Incomplete retrieval: {span} because RePORTER returns at most 10,000 records per query. "
            "The figure is a lower bound, not a complete total; narrow the query (fewer years, an agency "
            "or activity-code filter) for a complete figure."), STATES_INCOMPLETE))
    if keyword_topics:
        topics = ", ".join(f'"{t}"' for t in keyword_topics)
        found.append(Boundary("keyword_scope", (
            f"Scope: this is a keyword (text-search) cohort for {topics}, not an official NIH RCDC "
            "spending-category total. Text matching can include projects outside the intended area and miss "
            "others; for an official category figure, query by spending_category."), STATES_KEYWORD))
    return found


def enforce(question: str, answer: str, tool_results: list[dict]) -> dict:
    """Return the user-facing answer with every applicable boundary stated.

    Result: {"answer", "boundaries": [{id, added_by_guard}], "withheld_draft"?}.
    """
    answer = answer or ""
    cls = unsupported_class(question)
    if cls is not None:
        if ALREADY_DECLINED.search(answer):
            return {"answer": answer, "boundaries": [{"id": "unsupported_question", "class": cls,
                                                      "added_by_guard": False}]}
        what = UNSUPPORTED[cls][1]
        return {
            "answer": (f"This question is not supported: the NIH RePORTER tools here do not cover {what}, so "
                       "no answer is given rather than an estimate. Supported alternatives include funding "
                       "totals, trends, and award, organization or investigator lookups from RePORTER records."),
            "boundaries": [{"id": "unsupported_question", "class": cls, "added_by_guard": True}],
            "withheld_draft": answer,
        }

    boundaries, missing = [], []
    for b in detect(question, tool_results):
        b.added_by_guard = not all(rx.search(answer) for rx in b.stated)
        if b.added_by_guard:
            missing.append(b.caveat)
        boundaries.append({"id": b.id, "added_by_guard": b.added_by_guard})
    if missing:
        answer = (answer.rstrip() + "\n\nScope and limits (added automatically from the tool results):\n"
                  + "\n".join(f"- {c}" for c in missing))
    return {"answer": answer, "boundaries": boundaries}
