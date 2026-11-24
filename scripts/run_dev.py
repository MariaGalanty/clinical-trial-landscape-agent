"""Run the chain on all dev trials: summariser, then the trial agent for trials
still not_found. Saves one TrialSummary per line.

Makes real (billed) calls: 15 summariser calls, plus up to ~7 OpenAI calls and
up to 5 Tavily credits for each not_found trial.
"""

import json
from datetime import datetime
from pathlib import Path

from llm_log import LOG_PATH
from registry import flatten_study
from summarise import gather_abstracts, summarise_trial
from trial_agent import run_agent

project_root = Path(__file__).resolve().parent.parent
studies = json.loads(
    (project_root / "data/raw/als_studies_raw.json").read_text(encoding="utf-8")
)
rows_by_id = {r["nct_id"]: r for r in (flatten_study(s) for s in studies)}
split = json.loads((project_root / "eval/eval_split.json").read_text(encoding="utf-8"))

run_id = f"dev-{datetime.now():%Y%m%d-%H%M%S}"
out_path = project_root / "data/interim/runs" / f"chain_{run_id}.jsonl"
out_path.parent.mkdir(parents=True, exist_ok=True)

with out_path.open("w", encoding="utf-8") as f:
    for entry in split["dev"]:
        row = rows_by_id[entry["nct_id"]]
        abstracts = gather_abstracts(row)
        summary = summarise_trial(row, abstracts, run_id)
        before = summary.status
        if summary.status == "not_found":
            print(f"{row['nct_id']}  not_found -> running agent")
            summary = run_agent(row, abstracts, run_id)
        f.write(summary.model_dump_json() + "\n")
        print(
            f"{summary.nct_id}  {before:<16} -> {summary.status:<16} "
            f"claims={len(summary.claims)}  {summary.handler}"
        )

records = [json.loads(line) for line in LOG_PATH.open(encoding="utf-8")]
cost = sum(r.get("cost_usd") or 0 for r in records if r["run_id"] == run_id)
print(f"\nCost: ${cost:.4f}\nSaved: {out_path}")
