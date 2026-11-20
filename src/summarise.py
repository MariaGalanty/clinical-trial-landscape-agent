"""Summariser: one LLM call per trial, then a citation check in code."""

from datetime import datetime, timezone

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

from llm_log import logged_call
from schemas import ClaimSourceValidated, Source, Status, SummariserOutput, TrialSummary

MODEL = "gpt-5.4"
REASONING_EFFORT = "low"
HANDLER = f"summariser_v1_{REASONING_EFFORT}"  # bump v1 -> v2 when the prompt changes
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
- One fact per claim, as a short sentence.
- Every claim lists the labels of the sources that support it in source_refs,
  without the brackets (e.g. "34536404", "registry:why_stopped").
- A paper may be about a different trial (e.g. an earlier phase of the same drug).
  Only use a paper if it is clearly about THIS trial. Otherwise ignore it.
- If the sources say nothing about the outcome, return no claims.
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


def check_citations(
    output: SummariserOutput, sources: list[Source]
) -> tuple[list[ClaimSourceValidated], Status]:
    """Turn untrusted Claim into trusted ClaimSourceValidated. Any unknown source -> invalid_citation."""
    by_ref = {s.reference: s for s in sources}
    claims = []
    for c in output.claims:
        if not c.source_refs or any(ref not in by_ref for ref in c.source_refs):
            return [], "invalid_citation"
        claims.append(
            ClaimSourceValidated(
                text=c.text, topic=c.topic, sources=[by_ref[r] for r in c.source_refs]
            )
        )
    # Registry facts alone don't make a trial "found": need a paper or web source
    found = any(s.kind != "registry" for c in claims for s in c.sources)
    return claims, "found" if found else "not_found"


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


def summarise_trial(row: dict, abstracts: list[dict], run_id: str) -> TrialSummary:
    """Sources -> one LLM call -> citation check -> TrialSummary."""
    text, sources = build_sources(row, abstracts)
    base = registry_part(row, run_id)

    # Nothing to summarise -> no LLM call, no cost
    if not abstracts and not row.get("why_stopped"):
        return TrialSummary(
            **base, sources_fetched=sources, handler="skipped_no_sources"
        )

    response = logged_call(
        lambda: client.responses.parse(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=text,
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
        return TrialSummary(**base, sources_fetched=sources, handler=HANDLER)

    claims, status = check_citations(output, sources)
    return TrialSummary(
        **base,
        stop_category=output.stop_category,
        claims=claims,
        sources_fetched=sources,
        status=status,
        handler=HANDLER,
    )
