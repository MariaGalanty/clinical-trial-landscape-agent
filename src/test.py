from status_handler import handle_status
from router import route_trial
from why_stopped_handler import handle_why_stopped_llm

trial = {
    "nct_id": "NCT00000001",
    "overall_status": "RECRUITING",
}

status_evidence = handle_status(trial)

print(status_evidence)
assert status_evidence.status == "found"
assert status_evidence.question == "status"
assert status_evidence.nct_id == "NCT00000001"

missing_status_trial = {
    "nct_id": "NCT00000002",
}

missing_evidence = handle_status(missing_status_trial)

assert missing_evidence.status == "not_found"
assert missing_evidence.answer == ""

routed_evidence = route_trial(
    {
        "nct_id": "NCT00000003",
        "overall_status": "COMPLETED",
    },
    "status",
)

assert routed_evidence.nct_id == "NCT00000003"
assert routed_evidence.question == "status"
assert routed_evidence.status == "found"


try:
    route_trial(
        {
            "nct_id": "NCT00000004",
            "overall_status": "RECRUITING",
        },
        "results",  # type: ignore[arg-type]
    )
except ValueError as error:
    assert "Unsupported question" in str(error)
else:
    raise AssertionError("Unsupported question should fail")

routed_missing = route_trial(
    {
        "nct_id": "NCT00000005",
    },
    "status",
)

assert routed_missing.status == "not_found"
assert routed_missing.answer == ""
# assert routed_missing.handler == "status_registry_v1"


def test_status_router_uses_fallback() -> None:
    trial_without_status = {
        "nct_id": "NCT00000006",
    }

    evidence = route_trial(trial_without_status, "status")

    assert evidence.status == "not_found"
    assert evidence.answer == ""
    assert evidence.handler == "status_fallback_v1"


test_status_router_uses_fallback()
print("Fallback router test passed")


def test_why_stopped_without_text() -> None:
    # no why_stopped text, so no API call is made
    evidence = handle_why_stopped_llm({"nct_id": "NCT00000007"})

    assert evidence.status == "not_found"
    assert evidence.question == "why_stopped"
    assert evidence.category is None
    assert evidence.answer == ""
    assert evidence.handler == "why_stopped_llm_v1"


def test_why_stopped_slow_recruitment() -> None:
    # makes one real API call
    evidence = handle_why_stopped_llm(
        {
            "nct_id": "NCT00000008",
            "why_stopped": "Terminated due to slow recruitment",
        }
    )

    assert evidence.status == "found"
    assert evidence.category == "enrolment"
    assert evidence.answer != ""
    assert evidence.sources[0].reference == "why_stopped"


test_why_stopped_without_text()
test_why_stopped_slow_recruitment()
print("why_stopped handler tests passed")
