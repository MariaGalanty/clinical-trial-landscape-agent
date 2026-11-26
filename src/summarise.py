"""Summariser: one LLM call per trial, then a citation check in code."""

from datetime import datetime, timezone

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

from llm_log import logged_call
from schemas import ClaimSourceValidated, Source, Status, SummariserOutput, TrialSummary
from pubmed import fetch_abstract_cached, search_pubmed_cached

MODEL = "gpt-5.4"
REASONING_EFFORT = "low"
HANDLER = f"summariser_v5_{REASONING_EFFORT}"  # v5: status from claim topics (found / ongoing)
REGISTRY_FIELDS = ("brief_title", "overall_status", "why_stopped", "brief_summary")

INSTRUCTIONS = """You summarise what is known about the outcome of one clinical trial.

You get the trial's registry record and abstracts of papers. Each source starts
with a label in square brackets, e.g. [registry:why_stopped] or [34536404].

What to report:
- Completed trials: the result on the primary endpoint, and key safety findings.
- Stopped trials (TERMINATED, WITHDRAWN, SUSPENDED): why they stopped, and any results.
- Ongoing trials: progress, only if a source mentions it.

Rules:
- Use only the given sources. Do not use outside knowledge about the drug or sponsor.
- One fact per claim, as a short sentence. Report each fact only once.
- If several sources support the same fact, write ONE claim and list all of
  those sources in source_refs (e.g. ["28872918", "28872914"]).
- Every claim lists the labels of the sources that support it in source_refs,
  without the brackets (e.g. "34536404", "registry:why_stopped").
- A paper may be about a different trial (e.g. an earlier phase of the same drug).
  Only use a paper if it is clearly about THIS trial, or if its results affected
  this trial (e.g. an open-label extension stopped because the parent trial did
  not meet its primary endpoint). Otherwise ignore it.
- If the sources say nothing about the outcome, return no claims.
- Report outcomes only: results, safety findings, why the trial stopped, or
  progress. Do not report the trial's design (number of participants planned,
  dosing, arms, planned endpoints, duration): the registry already has it.
- stop_category: only for TERMINATED, WITHDRAWN or SUSPENDED trials; otherwise null.
"""

load_dotenv(find_dotenv())
client = OpenAI()  # reads OPENAI_API_KEY from .env


def build_sources(row: dict, abstracts: list[dict]) -> tuple[str, list[Source]]:
    """Labelled text for the prompt + the matching Source list, built together
    so the labels and the references can never drift apart."""
    parts, sources = [], []
    for field in REGISTRY_FIELDS:
        if row.get(field):
            ref = f"registry:{field}"
            parts.append(f"[{ref}]\n{row[field]}")
            sources.append(
                Source(
                    kind="registry",
                    reference=ref,
                    title=field,
                    role="trial_info",
                )
            )
    for a in abstracts:
        parts.append(f"[{a['pmid']}] {a['title']}\n{a['abstract']}")
        sources.append(
            Source(
                kind="pubmed",
                reference=a["pmid"],
                title=a["title"],
                role="trial_info",
            )
        )
    return "\n\n".join(parts), sources


STOPPED = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
ONGOING = {
    "RECRUITING",
    "ACTIVE_NOT_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
}
OUTCOME_TOPICS = {"results", "stop_reason"}


def decide_status(overall_status: str, claims: list[ClaimSourceValidated]) -> Status:
    """found = a paper/web page reports the outcome. Registry facts alone never count.

    - results or stop_reason from a paper/web page -> found
    - ongoing trial: progress from a paper/web page -> found; nothing new -> ongoing
    - finished/stopped/unknown trial with only progress news (e.g. "recruitment
      started in 2017") -> not_found: the outcome is still unknown
    """
    external = [c for c in claims if any(s.kind != "registry" for s in c.sources)]
    if any(c.topic in OUTCOME_TOPICS for c in external):
        return "found"
    if overall_status in ONGOING:
        return "found" if external else "ongoing"
    return "not_found"


def check_citations(
    output: SummariserOutput, sources: list[Source], overall_status: str
) -> tuple[list[ClaimSourceValidated], Status, list[str]]:
    """Turn untrusted Claim into trusted ClaimSourceValidated, then decide the status.

    A claim citing a source not given in this run (or no source) is dropped and
    reported in the third return value. invalid_citation only if claims were made
    but none survived."""
    by_ref = {s.reference: s for s in sources}
    claims, dropped = [], []
    for c in output.claims:
        unknown = [ref for ref in c.source_refs if ref not in by_ref]
        if not c.source_refs or unknown:
            bad = unknown or "(no sources)"
            print(f"  dropped claim, bad refs {bad}: {c.text[:100]}")
            dropped.append(f"{c.text} | bad refs: {bad}")
            continue
        claims.append(
            ClaimSourceValidated(
                text=c.text, topic=c.topic, sources=[by_ref[r] for r in c.source_refs]
            )
        )
    # Merge claims with the same text (ignoring case and spacing): one claim, all their sources
    merged: dict[str, ClaimSourceValidated] = {}
    for c in claims:
        key = " ".join(c.text.lower().split())
        if key in merged:
            known = {s.reference for s in merged[key].sources}
            merged[key].sources += [s for s in c.sources if s.reference not in known]
        else:
            merged[key] = c
    claims = list(merged.values())

    if dropped and not claims:
        return [], "invalid_citation", dropped
    return claims, decide_status(overall_status, claims), dropped


def registry_part(row: dict, run_id: str) -> dict:
    """The TrialSummary fields that come straight from the registry row."""
    return {
        "nct_id": row["nct_id"],
        "brief_title": row["brief_title"],
        "interventions": [i["name"] for i in row["interventions"]],
        "phases": row["phases"],
        "overall_status": row["overall_status"],
        "enrollment_count": row["enrollment_count"],
        "start_date": row["start_date"],
        "completion_date": row["completion_date"],
        "has_results": row["has_results"],
        "why_stopped_text": row["why_stopped"],
        "searched_at": datetime.now(timezone.utc),
        "run_id": run_id,
    }


TRIAL_REF_TYPES = (
    "RESULT",
    "DERIVED",
)  # registry reference types that are about this trial


def gather_abstracts(row: dict) -> list[dict]:
    """Fixed source gathering, no LLM: registry-linked papers + PubMed search by NCT ID."""
    linked = [
        r["pmid"]
        for r in row["references"]
        if r["type"] in TRIAL_REF_TYPES and r.get("pmid")
    ]
    searched = search_pubmed_cached(row["nct_id"])
    pmids = list(dict.fromkeys(linked + searched))  # merge, drop duplicates, keep order
    return [fetch_abstract_cached(p) for p in pmids]


def summarise_trial(row: dict, abstracts: list[dict], run_id: str) -> TrialSummary:
    """Sources -> one LLM call -> citation check -> TrialSummary."""
    text, sources = build_sources(row, abstracts)
    base = registry_part(row, run_id)

    # Nothing to summarise -> no LLM call, no cost
    if not abstracts and not row.get("why_stopped"):
        return TrialSummary(
            **base,
            sources_fetched=sources,
            status=decide_status(row["overall_status"], []),
            handler="skipped_no_sources",
        )

    response = logged_call(
        lambda: client.responses.parse(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=f"Trial: {row['nct_id']}\n\n{text}",
            text_format=SummariserOutput,
            reasoning={"effort": REASONING_EFFORT},
        ),
        provider="openai",
        model=MODEL,
        handler=HANDLER,
        nct_id=row["nct_id"],
        run_id=run_id,
    )
    output = response.output_parsed
    if output is None:  # model refused or was cut off
        return TrialSummary(
            **base,
            sources_fetched=sources,
            status=decide_status(row["overall_status"], []),
            handler=HANDLER,
        )

    claims, status, dropped = check_citations(output, sources, row["overall_status"])
    return TrialSummary(
        **base,
        stop_category=output.stop_category,
        claims=claims,
        sources_fetched=sources,
        status=status,
        dropped_claims=dropped,
        handler=HANDLER,
    )
