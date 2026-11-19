"""
Running tests for limited number of trails to test the code
Registry fetch is happending for all trials
"""

import json
import time
from pathlib import Path

from registry import fetch_all_studies, flatten_study
from pubmed import search_pubmed_cached, fetch_abstract_cached


CONDITION = "amyotrophic lateral sclerosis"

project_root = Path(__file__).resolve().parent.parent
raw_path = project_root / "data" / "raw" / "als_studies_raw.json"
split_path = project_root / "eval" / "eval_split.json"

# Fetch from the registery once, then reuse the saved snapshot
if raw_path.is_file():
    studies = json.loads(raw_path.read_text(encoding="utf-8"))
else:
    t0 = time.perf_counter()  # measuring how long a piece of code takes to run
    studies = fetch_all_studies(CONDITION)
    print(f"Registry fetch: {time.perf_counter() - t0:.1f}s")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(studies, ensure_ascii=False), encoding="utf-8")

rows = [flatten_study(s) for s in studies]
# drug_rows = [d for d in rows if is_drug_trial(d)]
# trials_sample = random.Random(SEED).sample(drug_rows, N_TRIALS)

# Loading only the dev trials for eval prompt enginnering
split = json.loads(split_path.read_text(encoding="utf-8"))
rows_by_id = {r["nct_id"]: r for r in rows}
dev_rows = [rows_by_id[entry["nct_id"]] for entry in split["dev"]]

run_start = time.perf_counter()
for row in dev_rows:
    t0 = time.perf_counter()
    trial_refs = [
        ref["pmid"] for ref in row["references"] if ref["type"] in ("RESULT", "DERIVED")
    ]
    background_refs = [
        ref["pmid"] for ref in row["references"] if ref["type"] == "BACKGROUND"
    ]
    pubmed_pmids = search_pubmed_cached(row["nct_id"])
    combined_trial_pmids = list(
        dict.fromkeys(trial_refs + pubmed_pmids)
    )  # no duplicates, order kept
    abstracts = [fetch_abstract_cached(pmid) for pmid in combined_trial_pmids]
    elapsed = time.perf_counter() - t0

    print(
        f"{row['nct_id']} | {row['overall_status']:<22} | "
        f"Trial refs: {len(combined_trial_pmids)} | from registry pmids {len(trial_refs)}| Background refs: {len(background_refs)}| PubMed by NCT: {combined_trial_pmids} | {elapsed:.2f}s"
    )

    for a in abstracts:
        print(f"  - {a['pmid']}: {a['title'][:100]}  ({len(a['abstract'])} chars)")

print(f"\nTotal: {time.perf_counter() - run_start:.1f}s for {len(dev_rows)} trials")
