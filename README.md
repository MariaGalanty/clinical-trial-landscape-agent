# Clinical Trial Landscape Agent

> **Work in progress.** The pipeline runs end to end on a development set of
> ALS trials, but the project is still being built: the full disease run, the
> evaluation and the demo are in the making. Expect changes.

Give it a disease (first: **ALS**), and it goes through every drug trial
registered for that disease and writes a short, **cited** summary of what is
known about each trial's outcome: did the drug work, was it safe, why was the
trial stopped, is it still running.

Every sentence points to the source it came from: a registry field, a PubMed
paper or a web page. If no source supports an answer, the trial is marked
`not_found` instead of guessed.

## Why this matters

ClinicalTrials.gov lists every trial, but it often does not say **how a trial
ended**. Results end up scattered across journal papers, conference abstracts,
company press releases and news articles, and many stopped trials give only a
one-line reason ("sponsor decision", "recommended by the DSMB"), or none.

For a disease like ALS, with hundreds of drug trials and very few approved
treatments, this matters:

- **Researchers and drug developers** need to know which mechanisms were
  already tried, what failed and why, before designing the next trial.
- **Patients and advocates** want to know what happened to the trials they
  heard about, or took part in.
- **Failed and stopped trials** are the hardest to find out about, and the
  most useful to learn from.

Doing this by hand takes hours per trial. Asking an LLM directly is fast, but
it may confuse trials of the same drug, or produce plausible text with no
source behind it. This project combines both: an LLM reads and summarises,
while code decides what can be cited and checks every citation.

## Golden rule

> Every claim cites a source that was actually fetched in the same run.
> A wrong "found" is worse than an honest "not_found".

This rule is enforced in code, not only asked for in the prompt.

## Example

A real output for the phase 2a trial of ANX005 in ALS (NCT04569435). The
registry and PubMed had nothing about its results, so the web agent searched
the web and read a news article about the trial:

```text
NCT04569435  Phase 2 trial of ANX005. Registry dates: 2021-01 to 2024-04. Status: completed.
  - [results] In January 2023, preliminary data from 8 patients showed slowing or halting of
    ALS Functional Rating Scale-Revised decline during the first 12 weeks of treatment.
      sources: https://alsnewstoday.com/news/annexon-anx005-slows-als-progression-phase-2-study
  - [results] In January 2023, the 6 patients who stopped treatment after 12 weeks were reported
    to decline functionally over the following 12 weeks.
      sources: https://alsnewstoday.com/news/annexon-anx005-slows-als-progression-phase-2-study
```

## How it works

```text
disease
  -> ClinicalTrials.gov snapshot, one record per trial                 [code]
  -> per trial:
       1. gather sources: registry fields, papers linked in the
          registry, PubMed search by NCT number                        [code]
       2. summariser: cited claims from these sources only             [LLM]
       3. if the outcome is still not found: web agent                 [agent]
       + citation check after each step                                [code]
  -> one TrialSummary per trial (claims, sources, status, cost)
every LLM call -> one line in a cost and latency log
```

### The summariser

Each source is given to the model with a label, such as
`[registry:why_stopped]`, `[28872918]` (a PMID) or a URL. The model returns
claims, each listing the labels it relies on. The model is told to report
outcomes only (results, safety, why a trial stopped, progress), each fact once,
and to use a paper only if it is clearly about **this** trial.

### The web agent

Built with LangGraph. It only runs for trials whose outcome is still unknown.

- **Code decides what to search.** The query is fixed by the trial's registry
  status, e.g. `NCT04569435 ALS results` for a completed trial or
  `NCT… ALS stopped` for a terminated one. Registry copies are excluded from
  the results (Tavily search).
- **The model decides what to read.** It sees the 10 results (title and
  snippet) and chooses which pages to fetch, one at a time, and when to stop.
- **Code sets the limits.** Only pages from the search results can be
  fetched, at most 5 per trial; then the graph goes straight to the final
  answer.
- **The agent explains itself.** It writes a short search note: what it found
  or could not find, and why. The note is kept for review and is never
  treated as evidence.

### The citation check

Done in code after every step:

- a claim survives only if every source it cites was actually given to the
  model in this run (a search snippet that was never fetched does not count);
- a claim with a bad or invented source is dropped and recorded, the others
  are kept;
- the trial status follows from the kept claims:

| Status | Meaning |
|---|---|
| `found` | a paper or web page reports the outcome: results or why the trial stopped (for ongoing trials, also progress news) |
| `ongoing` | the registry says the trial is still running, and no newer source was found |
| `not_found` | no source reports the outcome; registry facts alone never count |
| `invalid_citation` | the model made claims, but none of them could be verified |

### Design choices

- **A fixed chain, with one agent where it helps.** The pipeline is plain
  Python. The agent is used only for the hard trials, and its freedom is
  limited to choosing pages and when to stop.
- **Everything is cached.** PubMed searches, abstracts, web searches and pages
  are saved to disk (web requests under hashed file names), so prompts can be
  changed and rerun without fetching or paying for sources again, and every
  run sees the same sources.
- **Costs are measured.** Every LLM call is logged with its tokens, cost and
  latency, using a dated price list so the same run always gives the same
  cost.
- **Evaluation set made before any output.** 40 ALS trials were labelled by
  hand before the pipeline existed, and split into a development set (used
  while writing prompts) and a test set (kept for final numbers). No
  evaluation results are reported yet.

## Planned output

- one cited summary per drug trial;
- `landscape.csv`: one row per trial (drugs, phase, status, dates, number of
  claims and sources);
- `landscape.md`: a readable report, grouped by status and phase;
- a small read-only demo to browse the trials of a disease and their cited
  claims.

## Tech stack

Python 3.12, uv, Pydantic, OpenAI (Responses API, structured outputs),
LangGraph and LangChain, Tavily, NCBI E-utilities (PubMed),
ClinicalTrials.gov API v2.

## Repository layout

```text
src/        pipeline code
  registry.py      ClinicalTrials.gov fetch and flattening
  pubmed.py        PubMed search and abstract fetch, cached
  web.py           Tavily search and page extract, cached (hashed file names)
  schemas.py       Pydantic models: Source, Claim, TrialSummary, ...
  summarise.py     summariser prompt, citation check, trial status
  trial_agent.py   the LangGraph web agent
  llm_log.py       cost and latency log
  report.py        text from templates (no LLM)
scripts/    scripts run by hand (dev run, viewing a run, ...)
tests/      plain Python test scripts; saved PubMed XML in tests/fixtures/
eval/       frozen dev/test split and hand-made labels
config/     dated snapshot of LLM prices
docs/       the plan as PDF; notes from the first version in docs/archive/
PLAN.md     the original plan: scope, data models, evaluation
data/       downloaded data, caches and runs (not in git)
```

## Setup

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env    # then add your OpenAI and Tavily keys and an email for NCBI
uv run python tests/test_schemas.py
uv run python tests/test_pubmed.py   # downloads one PubMed record on first run
```

The tests are plain Python scripts with `assert`s and make no LLM calls.

`scripts/run_dev.py` runs the whole chain on the development trials and
`scripts/show_run.py` prints a saved run. **`run_dev.py` makes real, billed
OpenAI and Tavily calls**; the docstring at the top of each script says
whether it does.

## Licence

MIT, see [LICENCE](LICENCE).
