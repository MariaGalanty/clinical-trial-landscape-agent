"""Print a saved run (one TrialSummary per line), trial by trial. No API calls.

Usage:
  uv run python scripts/show_run.py                          # newest run file
  uv run python scripts/show_run.py <file>.jsonl             # a given run
  uv run python scripts/show_run.py <file>.jsonl NCT04569435 # only these trials
"""

import json
import sys
import textwrap
from pathlib import Path

from registry import flatten_study
from report import registry_summary
from schemas import TrialSummary


project_root = Path(__file__).resolve().parent.parent
runs_dir = project_root / "data/interim/runs"
files = [a for a in sys.argv[1:] if a.endswith(".jsonl")]
only = {a.upper() for a in sys.argv[1:] if a.upper().startswith("NCT")}
run_path = (
    Path(files[0])
    if files
    else max(runs_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
)

with run_path.open(encoding="utf-8") as f:
    summaries = [TrialSummary.model_validate_json(line) for line in f]
print(f"{run_path.name}: {len(summaries)} trials")

studies = json.loads(
    (project_root / "data/raw/als_studies_raw.json").read_text(encoding="utf-8")
)
brief_by_id = {
    row["nct_id"]: row["brief_summary"] for row in (flatten_study(s) for s in studies)
}

for t in summaries:
    if only and t.nct_id not in only:
        continue
    print(f"\n{'=' * 80}\n{t.nct_id} | {t.brief_title}\n{'=' * 80}")

    print("REGISTRY")
    print(f"  {registry_summary(t)}")
    brief = brief_by_id.get(t.nct_id) or "-"
    print("  Brief summary:")
    print(
        textwrap.fill(
            " ".join(brief.split()),
            width=100,
            initial_indent="    ",
            subsequent_indent="    ",
        )
    )
    print(
        f"  acronym: {t.acronym or '-'} | enrolment: {t.enrollment_count} | has_results: {t.has_results}"
    )
    print(f"  interventions: {t.interventions}")
    print(f"  primary endpoint: {t.primary_endpoint or '-'}")
    print(f"  why stopped: {t.why_stopped_text or '-'}")

    print("SUMMARY")
    print(f"  status: {t.status} | stop_category: {t.stop_category or '-'}")
    if not t.claims:
        print("  (no claims)")
    for i, c in enumerate(t.claims, 1):
        refs = ", ".join(s.reference for s in c.sources)
        print(f"  {i}. [{c.topic}] {c.text}\n     sources: {refs}")
    for d in t.dropped_claims:
        print(f"  DROPPED: {d}")

    print(f"SOURCES FETCHED ({len(t.sources_fetched)})")
    cited = {s.reference for c in t.claims for s in c.sources}
    for s in t.sources_fetched:
        mark = "cited" if s.reference in cited else "     "
        print(f"  {mark}  {s.kind:<8} {s.reference:<26} {s.title[:60]}")

    print("RUN")
    print(
        f"  handler: {t.handler} | tool calls: {t.n_tool_calls} | run: {t.run_id} | at: {t.searched_at:%Y-%m-%d %H:%M}"
    )
