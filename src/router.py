from typing import Any, Literal
from collections.abc import Callable

from evidence import Evidence
from status_handler import handle_status, handle_status_fallback


Handler = Callable[[dict[str, Any]], Evidence]
status_handlers: list[Handler] = [handle_status, handle_status_fallback]


def route_trial(
    trial: dict[str, Any],
    question: Literal["status"],
) -> Evidence:
    if question == "status":
        if not status_handlers:
            raise RuntimeError("No status handlers configured")
        for handler in status_handlers:
            evidence = handler(trial)
            if evidence.status == "found":
                return evidence
        return evidence  # returns the last result
    else:
        raise ValueError(f"Unsupported question: {question}")
