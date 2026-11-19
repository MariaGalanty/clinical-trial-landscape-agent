from datetime import datetime, timezone
from pydantic import ValidationError
from schemas import Claim, Source, TrialSummary

src = Source(kind="pubmed", reference="34536404", title="...", role="trial_info")
claim = Claim(
    text="The trial did not meet its primary endpoint.", topic="results", sources=[src]
)

record = TrialSummary(
    nct_id="NCT00000000",
    brief_title="Test",
    interventions=["Drug X"],
    phases=["PHASE3"],
    overall_status="COMPLETED",
    enrollment_count=100,
    start_date="2020-01",
    completion_date="2022-01",
    has_results=True,
    why_stopped_text=None,
    claims=[claim],
    handler="manual",
    searched_at=datetime.now(timezone.utc),
    run_id="test",
)
print("valid record OK")

try:
    Claim(text="Unsupported claim.", topic="results", sources=[])
    print("FAIL: claim without source was accepted")
except ValidationError:
    print("claim without source rejected OK")
