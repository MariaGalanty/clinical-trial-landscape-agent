"""Plain Python checks for router.py. None of them call the OpenAI API."""

from typing import Any

from evidence import Evidence
from router import route_trial, run_chain


# ---- Fake handlers: let us test run_chain without real handlers or an API ----

calls: list[str] = []  # records which fake handlers ran, in order


def make_evidence(status: str, handler: str) -> Evidence:
    return Evidence(
        nct_id="NCT_FAKE",
        question="status",
        answer="",
        category=None,
        status=status,  # type: ignore[arg-type]
        handler=handler,
        n_tool_calls=0,
    )


def fake_not_found(trial: dict[str, Any]) -> Evidence:
    calls.append("fake_not_found")
    return make_evidence("not_found", "fake_not_found")


def fake_found(trial: dict[str, Any]) -> Evidence:
    calls.append("fake_found")
    return make_evidence("found", "fake_found")


def fake_never_called(trial: dict[str, Any]) -> Evidence:
    calls.append("fake_never_called")
    return make_evidence("found", "fake_never_called")


# ---- run_chain ----


def test_run_chain_stops_at_first_found() -> None:
    calls.clear()
    evidence = run_chain([fake_not_found, fake_found, fake_never_called], {})

    assert evidence.handler == "fake_found"
    assert calls == ["fake_not_found", "fake_found"]  # third handler skipped


def test_run_chain_returns_last_when_nothing_found() -> None:
    calls.clear()
    evidence = run_chain([fake_not_found, fake_not_found], {})

    assert evidence.status == "not_found"
    assert calls == ["fake_not_found", "fake_not_found"]


def test_run_chain_empty_list_raises() -> None:
    try:
        run_chain([], {})
    except RuntimeError as error:
        assert "No handlers configured" in str(error)
    else:
        raise AssertionError("Empty handler list should fail")


# ---- route_trial ----


def test_status_route_found() -> None:
    evidence = route_trial({"nct_id": "NCT00000010", "overall_status": "COMPLETED"}, "status")

    assert evidence.status == "found"
    assert evidence.handler == "status_registry_v1"


def test_status_route_uses_fallback() -> None:
    evidence = route_trial({"nct_id": "NCT00000011"}, "status")

    assert evidence.status == "not_found"
    assert evidence.handler == "status_fallback_v1"


def test_why_stopped_route_uses_why_stopped_chain() -> None:
    # no why_stopped text, so the handler returns early without an API call
    evidence = route_trial({"nct_id": "NCT00000012"}, "why_stopped")

    assert evidence.question == "why_stopped"
    assert evidence.status == "not_found"
    assert evidence.handler == "why_stopped_llm_v1"


def test_unsupported_question_raises() -> None:
    try:
        route_trial({"nct_id": "NCT00000013"}, "results")  # type: ignore[arg-type]
    except ValueError as error:
        assert "Unsupported question" in str(error)
    else:
        raise AssertionError("Unsupported question should fail")


tests = [
    test_run_chain_stops_at_first_found,
    test_run_chain_returns_last_when_nothing_found,
    test_run_chain_empty_list_raises,
    test_status_route_found,
    test_status_route_uses_fallback,
    test_why_stopped_route_uses_why_stopped_chain,
    test_unsupported_question_raises,
]

failed = 0
for test in tests:
    try:
        test()
        print(f"PASS  {test.__name__}")
    except AssertionError as error:
        failed += 1
        print(f"FAIL  {test.__name__}  {error}")

print(f"\n{len(tests) - failed} passed, {failed} failed")
