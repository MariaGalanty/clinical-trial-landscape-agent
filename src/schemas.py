"""Data models (schemas) for the pipeline.  The LLM fills SummariserOutput; code builds the rest."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceKind = Literal["registry", "pubmed", "web"]
SourceRole = Literal["trial_info", "background_info"]
Topic = Literal["stop_reason", "results", "progress"]
StopCategory = Literal[
    "efficacy_futility", "safety", "business_strategic", "enrolment", "other", "unclear"
]
# found: a paper/web page reports the outcome (results or stop reason; for ongoing trials also progress)
# ongoing: registry says the trial is ongoing and no newer source was found
Status = Literal["found", "ongoing", "not_found", "invalid_citation"]


class Source(BaseModel):
    kind: SourceKind
    reference: str  # registry field name, PMID or URL
    title: str = ""
    role: SourceRole


class ClaimSourceValidated(BaseModel):
    """One claim that passed the citation check (trusted).

    Built by code from a Claim: every source here was really fetched in this
    run. A claim must have at least one source. This is what gets stored in
    TrialSummary and written to the landscape files.
    """

    text: str
    topic: Topic
    sources: list[Source] = Field(min_length=1)  # a claim without a source is invalid


# --- What the LLM returns (kept small: output tokens are the expensive ones) ---


class Claim(BaseModel):
    """One claim as returned by the LLM (untrusted).

    source_refs are the labels the LLM copied from the prompt, e.g. "34536404"
    or "registry:why_stopped". They may be invented, so they are checked by
    check_citations before anything is stored.
    """

    text: str
    topic: Topic
    source_refs: list[str]  # PMIDs or registry field names, as given in the prompt


class SummariserOutput(BaseModel):
    stop_category: StopCategory | None
    claims: list[Claim]


class AgentOutput(SummariserOutput):
    """What the web agent returns: the summariser's output + a note on its search."""

    search_note: str  # what was searched and read, and why the outcome was or wasn't found


# ------ The full record, assembled by code ---
class TrialSummary(BaseModel):
    # from the trial registery, no LLM
    nct_id: str
    brief_title: str
    acronym: str | None = None
    interventions: list[str]
    phases: list[str]
    overall_status: str
    enrollment_count: int | None
    start_date: str | None
    completion_date: str | None
    primary_endpoint: str | None = None
    has_results: bool
    why_stopped_text: str | None

    # from the summariser - LLM/agent
    stop_category: StopCategory | None = (
        None  # ONE label, stopped trials only: "safety", "enrolment", ...
    )
    claims: list[
        ClaimSourceValidated
    ] = []  # THE SUMMARY: all sentences, any topic (results, stop_reason, progress)
    sources_fetched: list[Source] = []  # everything that was fetched, cited or not

    # from the citation check
    status: Status = "not_found"
    dropped_claims: list[str] = []  # claims removed by the citation check, with their bad refs
    search_note: str | None = None  # from the web agent: what it searched and why it stopped (not evidence)

    # about the run
    handler: str
    n_tool_calls: int = 0
    searched_at: datetime
    run_id: str
