# Clinical Trial Landscape Agent

> **Work in progress.** The pipeline is being built step by step. The parts
> marked ✅ below exist; everything else is planned. There are no evaluation
> results yet. The full plan is in [PLAN.md](PLAN.md).

Give it a disease name (first: **ALS**), and it lists every drug trial for
that disease with a short, **cited** summary of what is known about each
trial's outcome: did it work, why was it stopped, is it still running.

**Golden rule:** every sentence cites a source that was fetched in the same
run (a registry field, a PubMed ID or a URL). If no source supports an answer,
the trial is marked `not_found`. A wrong answer is worse than an honest "not
found".

## Why

ClinicalTrials.gov lists thousands of trials, but often does not say how they
ended. Results are spread across papers, press releases and conference
abstracts, and many stopped trials only give a one-line reason. This project
collects that evidence per trial and keeps every claim traceable to its
source, so a reader can check it.

## Planned output

For one disease:

- **one trial summary per drug trial:** short sentences, each citing its
  source;
- **`landscape.csv`:** one row per trial (drug names, phase, status,
  enrolment, dates, summary status, number of sources);
- **`landscape.md`:** a readable report, grouped by status and phase.

## How it works (planned)

```text
disease
  -> fetch all trials from ClinicalTrials.gov, save a raw snapshot   [code]
  -> keep trials with a real drug intervention                       [code]
  -> per trial, stop at the first "found":
       1. gather sources: registry facts, linked papers,
          PubMed search by NCT ID and acronym                        [code]
       2. summariser: cited sentences from these sources only        [LLM]
       3. if still not_found: search agent with PubMed free-text
          search and web search, max 5 tool calls                    [agent]
       + citation check after each step                              [code]
  -> landscape.csv + landscape.md                                    [code]
every LLM call -> one line in a cost and latency log
```

Design choices:

- **A fixed chain, not a multi-agent system.** The chain is plain Python.
  An agent (LangGraph) is used only for the hard trials where the fixed
  search finds nothing.
- **A citation check in code.** Every claim must cite a source that was
  actually fetched. A made-up PMID is caught and the trial is marked
  `invalid_citation`.
- **Every fetch is cached on disk**, so prompts can be rerun without
  fetching from PubMed again.
- **Evaluated against hand-made labels.** 40 ALS trials were labelled by hand
  *before* any summariser output was seen, and split into a dev set (prompt
  writing) and a test set (final numbers only). See
  [eval/README.md](eval/README.md).

## Status

| # | Step | Status |
|---|---|---|
| 1 | Registry fetch and drug-trial filter | ✅ first version; snapshot and filter rules still to finish |
| 2 | Data models (Pydantic) | ✅ |
| 3 | Source gathering: PubMed search and abstract fetch, disk cache | ✅ |
| 4 | Hand-labelled evaluation set (15 dev + 25 test trials) | ✅ |
| 5 | LLM summariser + citation check + cost log | 🔧 first version, being tested on dev trials |
| 6 | Full ALS run → `landscape.csv` + `landscape.md` | to do |
| 7 | Evaluate the fixed pipeline | to do |
| 8 | Search agent (LangGraph, PubMed + web search) | to do |
| 9 | Evaluate the agent | to do |
| 10 | CLI, Docker | to do |
| 11 | Read-only FastAPI demo (v2) | later |

## Repository layout

```text
src/        pipeline code: registry, pubmed, schemas, summarise, llm_log
scripts/    scripts run by hand (make the eval split, try the summariser, ...)
tests/      plain Python test scripts; saved PubMed XML in tests/fixtures/
eval/       frozen dev/test split and hand-made labels
config/     dated snapshot of LLM prices, used for the cost log
data/       downloaded and processed data (not in git)
docs/       plan as PDF; notes from the first version in docs/archive/
PLAN.md     the full plan: scope, data models, evaluation, steps
```

## Setup

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env    # then add OPENAI_API_KEY=... to .env
uv run python tests/test_schemas.py
uv run python tests/test_pubmed.py   # downloads one PubMed record on first run
```

The tests are plain Python scripts with `assert`s, run one by one. No LLM
calls.

There is no single command to run the pipeline yet (step 6). The scripts in
`scripts/` run single parts. Some of them make real, billed OpenAI calls;
the docstring at the top of each script says so.

## Licence

MIT, see [LICENCE](LICENCE).
