from status_handler import handle_status
from router import route_trial

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
