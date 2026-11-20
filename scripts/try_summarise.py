"""Try the summariser: 1) offline citation-check tests (free), 2) a real run on 3 dev trials."""

import json
from datetime import datetime
from pathlib import Path

from llm_log import LOG_PATH
from pubmed import fetch_abstract_cached, search_pubmed_cached
from registry import flatten_study
from schemas import Claim, Source, SummariserOutput
from summarise import check_citations, summarise_trial

N_REAL_TRIALS = 10

# --- 1. Offline tests of the citation check (no API call, no cost) ---------
sources = [
    Source(
        kind="registry",
        reference="registry:why_stopped",
        title="why_stopped",
        role="trial_info",
    ),
    Source(kind="pubmed", reference="34536404", title="Some paper", role="trial_info"),
]


def fake_output(refs: list[str]) -> SummariserOutput:
    return SummariserOutput(
        stop_category=None,
        claims=[Claim(text="A claim.", topic="results", source_refs=refs)],
    )


_, status = check_citations(fake_output(["34536404"]), sources)
assert status == "found", status
_, status = check_citations(fake_output(["99999999"]), sources)  # invented PMID
assert status == "invalid_citation", status
_, status = check_citations(
    fake_output(["registry:why_stopped"]), sources
)  # registry only
assert status == "not_found", status
_, status = check_citations(fake_output([]), sources)  # no source at all
assert status == "invalid_citation", status
print("Offline citation-check tests: OK\n")

# --- 2. Real run on a few dev trials that have something to summarise ------
project_root = Path(__file__).resolve().parent.parent
studies = json.loads(
    (project_root / "data" / "raw" / "als_studies_raw.json").read_text(encoding="utf-8")
)
rows_by_id = {r["nct_id"]: r for r in (flatten_study(s) for s in studies)}
split = json.loads(
    (project_root / "eval" / "eval_split.json").read_text(encoding="utf-8")
)

run_id = "try-" + datetime.now().strftime("%Y%m%d-%H%M%S")
n_done = 0
for entry in split["dev"]:
    row = rows_by_id[entry["nct_id"]]
    trial_refs = [
        r["pmid"] for r in row["references"] if r["type"] in ("RESULT", "DERIVED")
    ]
    pmids = list(dict.fromkeys(trial_refs + search_pubmed_cached(row["nct_id"])))
    abstracts = [fetch_abstract_cached(p) for p in pmids]
    if not abstracts and not row.get("why_stopped"):
        continue  # nothing to summarise -> skip, we want to exercise the LLM here

    summary = summarise_trial(row, abstracts, run_id)
    print(f"{row['nct_id']} | {row['overall_status']} | {row['brief_title'][:80]}")
    print(
        f"  status: {summary.status} | stop_category: {summary.stop_category} | papers: {len(abstracts)}"
    )
    for c in summary.claims:
        refs = ", ".join(s.reference for s in c.sources)
        print(f"    [{c.topic}] {c.text}  ({refs})")
    print()

    n_done += 1
    if n_done == N_REAL_TRIALS:
        break

# --- 3. What did it cost? -------------------------------------------------
records = [json.loads(line) for line in LOG_PATH.open(encoding="utf-8")]
this_run = [r for r in records if r["run_id"] == run_id]
for r in this_run:
    print(
        f"{r['nct_id']}: ok={r['ok']} latency={r['latency_s']}s "
        f"in={r.get('uncached_input')} cached={r.get('cached_input')} "
        f"out={r.get('output')} (reasoning {r.get('reasoning')}) cost=${r.get('cost_usd')}"
    )
