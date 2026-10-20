from typing import Any, Literal
from collections.abc import Callable

from evidence import Evidence
from status_handler import handle_status, handle_status_fallback
from why_stopped_handler import handle_why_stopped_llm


Handler = Callable[[dict[str, Any]], Evidence]
status_handlers: list[Handler] = [handle_status, handle_status_fallback]
why_stopped_handlers: list[Handler] = [handle_why_stopped_llm]


def run_chain(handlers: list[Handler], trial: dict[str, Any]) -> Evidence:
    if not handlers:
        raise RuntimeError("No handlers configured")
    for handler in handlers:
        evidence = handler(trial)
        if evidence.status == "found":
            return evidence
    return evidence


def route_trial(
    trial: dict[str, Any],
    question: Literal["status", "why_stopped"],
) -> Evidence:
    if question == "status":
        return run_chain(status_handlers, trial)
    elif question == "why_stopped":
        return run_chain(why_stopped_handlers, trial)
    else:
        raise ValueError(f"Unsupported question: {question}")
