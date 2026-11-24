"""Run the summariser on ONE trial and print every step.

Makes one real (billed) OpenAI call.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import summarise as s  # "s." makes it clear what comes from summarise.py
from llm_log import LOG_PATH, logged_call
from pubmed import fetch_abstract_cached, search_pubmed_cached
from registry import flatten_study
from schemas import SummariserOutput, TrialSummary

# N_TRIALS = 3  # how many dev trials to inspect
PER_GROUP = 1  # how many trials per each category
NCT_IDS: list[str] = []  # or pick by hand, e.g. ["NCT04569435", "NCT00424463"]
SHOW_PROMPT_CHARS = 0  # 1500  # how much of the prompt to print (0 = none)

project_root = Path(__file__).resolve().parent.parent
studies = json.loads(
    (project_root / "data" / "raw" / "als_studies_raw.json").read_text(encoding="utf-8")
)
rows_by_id = {r["nct_id"]: r for r in (flatten_study(st) for st in studies)}
split = json.loads(
    (project_root / "eval" / "eval_split.json").read_text(encoding="utf-8")
)
run_id = "inspect-" + datetime.now().strftime("%Y%m%d-%H%M%S")

PER_GROUP = 1  # how many trials per each category


def pick_nct_ids() -> list[str]:
    # 1. IDs on the command line (Jupyter adds "--f=..." args, so keep only NCT IDs)
    cli_args = [a.upper() for a in sys.argv[1:] if a.upper().startswith("NCT")]
    if cli_args:
        return cli_args
    # 2. IDs set by hand in NCT_IDS
    if NCT_IDS:
        return NCT_IDS
    # 3. The first PER_GROUP dev trials of each group, from eval_split.json
    picked = []
    for group in ("completed", "stopped", "ongoing_or_unknown"):
        in_group = [e["nct_id"] for e in split["dev"] if e["group"] == group]
        picked += in_group[:PER_GROUP]
    return picked


def step(n: int, title: str) -> None:
    print(f"\n----------- STEP {n}: {title}")


def inspect(nct_id: str) -> dict:
    """All steps for the one trial. Returns one row for the overview table"""
    row = rows_by_id[nct_id]
    print(
        f"\n{'=' * 70}\n{nct_id} | {row['overall_status']} | {row['brief_title'][:70]}\n{'=' * 70}"
    )

    # 1. Registry row (no LLM)
    step(1, "registry row")
    for field in ("why_stopped", "phases", "has_results", "references"):
        print(f"{field}: {row.get(field)}")

    # 2. Gather papers (cached, no LLM)
    step(2, "gather papers")
    trial_refs = [
        r["pmid"] for r in row["references"] if r["type"] in ("RESULTS", "DERIVED")
    ]
    search_pmids = search_pubmed_cached(nct_id)
    pmids = list(dict.fromkeys(trial_refs + search_pmids))
    print(
        f"  registry refs: {trial_refs} | PubMed by NCT: {search_pmids} | combined: {pmids}"
    )
    abstracts = [fetch_abstract_cached(p) for p in pmids]
    for a in abstracts:
        print(f" - {a['pmid']}: {a['title'][:90]} ({len(a['abstract'])} charts)")

    # 3. What the LLM will see
    step(3, "build sources")
    text, sources = s.build_sources(row, abstracts)
    print(f"  {len(sources)} sources: {[src.reference for src in sources]}")
    print(
        f" prompt: {len(text)} chars (~{len(text) // 4} tokens"
    )  # ~ just an estimate that 1 token per 4 characters
    if SHOW_PROMPT_CHARS:
        print(
            "Prompt chars: "
            + text[:SHOW_PROMPT_CHARS]
            + ("\n  ...[cut]" if len(text) > SHOW_PROMPT_CHARS else "")
        )

    result = {
        "nct_id": nct_id,
        "status": "skipped",
        "claims": 0,
        "papers": len(abstracts),
        "latency_s": None,
        "cost_usd": None,
    }

    if not abstracts and not row.get("why_stopped"):
        print("  Nothing to summarise -> skipped, no LLM call.")
        # 6. The record that would be saved: registry facts only, no claims
        step(6, "TrialSummary (registry only)")
        summary = TrialSummary(
            **s.registry_part(row, run_id),
            sources_fetched=sources,
            handler="skipped_no_sources",
        )  # status stays "not_found", the default
        print(summary.model_dump_json(indent=2, exclude={"sources_fetched"}))
        return result

    # 4. LLM call -> untrusted Claims
    step(4, f"LLM call ({s.MODEL}, effort={s.REASONING_EFFORT})")
    response = logged_call(
        lambda: s.client.responses.parse(
            model=s.MODEL,
            instructions=s.INSTRUCTIONS,
            input=text,
            text_format=SummariserOutput,
            reasoning={"effort": s.REASONING_EFFORT},
        ),
        provider="openai",
        model=s.MODEL,
        handler=s.HANDLER,
        nct_id=nct_id,
        run_id=run_id,
    )
    log = json.loads(LOG_PATH.read_text(encoding="utf-8").splitlines()[-1])
    result.update(latency_s=log["latency_s"], cost_usd=log["cost_usd"])

    output = response.output_parsed
    print(f"Output: {output}")
    if output is None:
        print("  No parsed output (refused or cut off).")
        result["status"] = "no_output"
        return result

    known = {src.reference for src in sources}
    print(f"  stop_category: {output.stop_category}")
    for c in output.claims:
        checked = [f"{r} ({'ok' if r in known else 'UNKNOWN'})" for r in c.source_refs]
        print(f"  [{c.topic}] {c.text}\n      source_refs: {checked}")

    # 5. Citation check (code)
    step(5, "check_citations")
    claims, status = s.check_citations(output, sources)
    print(f"  status: {status} | claims kept: {len(claims)} of {len(output.claims)}")

    # 6. The record that would be saved
    step(6, "TrialSummary")
    summary = TrialSummary(
        **s.registry_part(row, run_id),
        stop_category=output.stop_category,
        claims=claims,
        sources_fetched=sources,
        status=status,
        handler=s.HANDLER,
    )
    print(summary.model_dump_json(indent=2, exclude={"sources_fetched"}))

    # 7. Cost and latency
    step(7, "cost and latency")
    print(
        f"  {log['latency_s']} s | in {log['uncached_input']} (+{log['cached_input']} cached) "
        f"| out {log['output']} (reasoning {log['reasoning']}) | ${log['cost_usd']}"
    )

    result.update(status=status, claims=len(claims))
    return result


# ---- Run and compare
results = []

for nct_id in pick_nct_ids():
    if nct_id not in rows_by_id:
        print(f"\n{nct_id} is not in the ALS snapshot - skipped")
        continue
    results.append(inspect(nct_id))

from registry import flatten_study

split = json.loads(
    Path(project_root / "eval/eval_split.json").read_text(encoding="utf-8")
)
studies = json.loads(
    Path(project_root / "data/raw/als_studies_raw.json").read_text(encoding="utf-8")
)
rows_by_id = {r["nct_id"]: r for r in (flatten_study(st) for st in studies)}

for name in ("dev", "test"):
    print(f"\n{name} ({len(split[name])} trials)")
    for e in split[name]:
        row = rows_by_id[e["nct_id"]]
        phases = "/".join(row["phases"] or []) or "-"
        print(f"  {e['nct_id']}  {e['status']:<20} {phases}")
        print(f"{e['title']}")
        refs = row["references"]
        refs_text = ", ".join(
            f"{r['pmid']} ({r['type']})" for r in refs if r.get("pmid")
        )
        print(f"      registry PMIDs: {refs_text or '-'}")
        print("-" * 60)
