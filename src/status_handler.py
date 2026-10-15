from typing import Any
from evidence import Evidence, Source


def handle_status(trial: dict[str, Any]) -> Evidence:
    nct_id = trial.get("nct_id")
    overall_status = trial.get("overall_status")
    # If overall_status is missing or empty, return not_found.
    if not nct_id or not overall_status:
        return Evidence(
            nct_id=nct_id or "unknown",
            question="status",
            answer="",
            category=None,
            sources=[],
            status="not_found",
            handler="status_registry_v1",
            n_tool_calls=0,
        )
    answer = f"The current status of the trial is {overall_status}"
    status_evidence = Evidence(
        nct_id=nct_id,
        question="status",
        answer=answer,
        category=None,
        sources=[Source(kind="registry", reference="overall_status")],
        status="found",
        handler="status_registry_v1",
        n_tool_calls=0,
    )
    return status_evidence


def handle_status_fallback(trial: dict[str, Any]) -> Evidence:
    nct_id = trial.get("nct_id") or "unknown"

    return Evidence(
        nct_id=nct_id,
        question="status",
        answer="",
        category=None,
        sources=[],
        status="not_found",
        handler="status_fallback_v1",
        n_tool_calls=0,
    )
