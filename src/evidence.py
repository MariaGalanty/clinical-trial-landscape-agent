from typing import Literal
from pydantic import BaseModel, Field


class Source(BaseModel):
    kind: Literal["registry", "pubmed", "web"]  # what type of source it is
    reference: str  # how to locate the exact source


Category = Literal[
    "efficacy_futility",  # The treatment did not work, or was unlikely to work
    "safety",  # Adverse events, toxicity, or safety concerns
    "business_strategic",  # Funding, company strategy, acquisition, regulatory, or commercial reasons
    "enrolment",  # Difficulty recruiting or retaining enough participants
    "other",  # A specific reason that does not fit the categories above
    "unclear",  # The explanation is too vague to classify confidently
]


class WhyStoppedLabel(BaseModel):
    reason: str = Field(description="One short sentence explaining the choice")
    category: Category


class Evidence(BaseModel):
    nct_id: str
    question: Literal["why_stopped", "results", "status"]
    answer: str
    category: Category | None
    sources: list[Source] = Field(default_factory=list)
    status: Literal["found", "not_found", "invalid_citation"]
    handler: str
    n_tool_calls: int
