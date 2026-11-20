"""
Create the frozen dev/test split for evaluation. Run ONCE, then commit the file.
Mostly needed for llm prompt engineering
"""

import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

from registry import flatten_study, is_drug_trial


"""Create the frozen dev/test split for evaluation. Run ONCE, then commit the file."""
import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

from registry import flatten_study, is_drug_trial

SEED = 42
# group -> (n_dev, n_test)
SIZES = {"stopped": (5, 8), "completed": (5, 9), "ongoing_or_unknown": (5, 8)}

project_root = Path(__file__).resolve().parent.parent
raw_path = project_root / "data" / "raw" / "als_studies_raw.json"
split_path = project_root / "eval" / "eval_split.json"

if split_path.is_file():
    raise SystemExit(
        f"{split_path} already exists - the split is frozen. Delete it only on purpose."
    )


def status_group(status: str) -> str:
    if status in ("TERMINATED", "WITHDRAWN", "SUSPENDED"):
        return "stopped"
    if status == "COMPLETED":
        return "completed"
    return "ongoing_or_unknown"


studies = json.loads(raw_path.read_text(encoding="utf-8"))
rows = [flatten_study(s) for s in studies]
eligible = [r for r in rows if is_drug_trial(r) and r["study_type"] == "INTERVENTIONAL"]
# for now exclude e.g., expanded access protocols

by_group = defaultdict(list)
for r in eligible:
    by_group[status_group(r["overall_status"])].append(r)

rng = random.Random(SEED)
split = {
    "created": date.today().isoformat(),
    "seed": SEED,
    "snapshot": raw_path.name,
    "dev": [],
    "test": [],
}
for group in sorted(SIZES):
    n_dev, n_test = SIZES[group]
    candidates = sorted(
        by_group[group], key=lambda r: r["nct_id"]
    )  # order independent of the API
    picked = rng.sample(candidates, n_dev + n_test)
    for i, r in enumerate(picked):
        entry = {
            "nct_id": r["nct_id"],
            "group": group,
            "status": r["overall_status"],
            "title": r["brief_title"],
        }
        split["dev" if i < n_dev else "test"].append(entry)

split_path.parent.mkdir(parents=True, exist_ok=True)
split_path.write_text(json.dumps(split, indent=2, ensure_ascii=False), encoding="utf-8")

print(
    f"Eligible trials: {len(eligible)}  "
    + ", ".join(f"{g}: {len(v)}" for g, v in sorted(by_group.items()))
)
print(f"Saved dev={len(split['dev'])}, test={len(split['test'])} to {split_path}")
