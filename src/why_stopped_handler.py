import os
from typing import Any

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
from evidence import WhyStoppedLabel, Evidence, Source

MODEL = "gpt-5.4-nano"
WHY_STOPPED_LLM_VERSION = "v1"
INSTRUCTIONS = """ You classify why a clinical trial was stopped, using the "why stopped"
text from its ClinicalTrials.gov registry record.

Categories:
- efficacy_futility: the treatment did not work, or an analysis showed it was unlikely to work
- safety: adverse events, toxicity, or other safety concerns
- business_strategic: funding, sponsor or company strategy, acquisition, regulatory, or commercial reasons
- enrolment: difficulty recruiting or retaining enough participants
- other: a specific, stated reason that fits none of the above (e.g. drug supply problems, PI left the institution)
- unclear: no real reason is given, or the text is too vague to classify

Rules:
- Use only the given text. Do not guess using outside knowledge about the drug or sponsor.
- Classify the root cause, not its consequences. "Terminated by sponsor due to slow recruitment"
  is enrolment, because the sponsor decision was caused by recruitment.
- If several independent reasons are given, choose the first one that applies in this order:
  safety, efficacy_futility, enrolment, business_strategic, other.
- A bare sponsor, funder, or business decision with no stated reason is unclear.
- Phrases like "no recruitment" or "no data collected" describe the result of stopping early.
  They are not enrolment unless the text says recruitment problems caused the stop.
  Example: "Terminated by funder before recruitment started, no patients enrolled" is unclear,
  because the funder's reason is not stated.
"""


def classify_why_stopped(text: str) -> WhyStoppedLabel | None:
    load_dotenv(find_dotenv())
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set — check your .env file")

    client = OpenAI()
    response = client.responses.parse(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=text,
        text_format=WhyStoppedLabel,
    )
    return response.output_parsed  # None if the model refused or was cut off


def handle_why_stopped_llm(trial: dict[str, Any]) -> Evidence:
    text = trial.get("why_stopped")
    nct_id = trial.get("nct_id") or "unknown"
    question = "why_stopped"
    sources: list[Source]
    if not text:  # missing or empty: no API call
        answer = ""
        category = None
        sources = []
        status = "not_found"
    else:
        label = classify_why_stopped(text)
        if label is None:  # model refused or was cut off
            answer = ""
            category = None
            sources = []
            status = "not_found"
        elif label.category == "unclear":  # keep the label, but let later handlers run
            answer = label.reason
            category = label.category
            sources = [Source(kind="registry", reference="why_stopped")]
            status = "not_found"
        else:
            answer = label.reason
            category = label.category
            sources = [Source(kind="registry", reference="why_stopped")]
            status = "found"

    why_stopped_evidence = Evidence(
        nct_id=nct_id,
        question=question,
        answer=answer,
        category=category,
        sources=sources,
        status=status,
        handler=f"why_stopped_llm_{WHY_STOPPED_LLM_VERSION}",
        n_tool_calls=0,  # LLM calls are not tool calls; PubMed searches will be
    )

    return why_stopped_evidence


if __name__ == "__main__":
    trials = [
        {"nct_id": "NCT_TEST_1"},  # no why_stopped, so no API call
        {"nct_id": "NCT_TEST_2", "why_stopped": "Terminated due to slow recruitment"},
        {
            "nct_id": "NCT_TEST_3",
            "why_stopped": "Study terminated by funder- terminated before CCC and "
            "recruitment- no recruitment and no data collection",
        },
    ]
    for trial in trials:
        print(handle_why_stopped_llm(trial))
