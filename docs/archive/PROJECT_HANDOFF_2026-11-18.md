# Project Handoff

## Project

Clinical-trial landscape agent. Input: a disease name (so far: ALS). Output:
an evidence-grounded overview of every drug tested for that disease, built
in three levels:

```text
1. Trial summary    per trial: what do we know about its outcome?
                    sources: registry fields + PubMed articles + web search
2. Drug summary     per drug: its trials by phase, summarised from level 1
3. Landscape        per disease: all drugs, summarised from level 2,
                    plus landscape.csv and a Markdown dossier per drug
```

**Changed on 2026-11-18:** the project used to focus on *why trials stopped*.
It now summarises the outcome of *every* trial (stopped, completed or
ongoing), then rolls up to drugs and the disease. The stop-reason classifier
from Step 5 stays: for stopped trials, its category becomes one field of the
trial summary.

Golden rule, at every level: **every claim cites its source, otherwise the
answer is "not found".**
- A trial summary cites registry fields, PMIDs and URLs that were fetched in
  this run.
- A drug summary cites only trial summaries (NCT IDs), not the model's memory.
- The landscape cites only drug summaries and trials.

The model provider should remain replaceable: OpenAI first, later Ollama or
another local model.

## Learning agreement

This is a learning project. The assistant should:

- explain concepts before implementation;
- use small toy examples unrelated to the project;
- give the learner a focused task;
- avoid writing whole files or features unless explicitly requested;
- review learner-written code for bugs first, then readability;
- ask check-your-understanding questions before moving to the next concept;
- use Pylance/runtime checks and explain what they show.

The learner prefers plain Python test scripts. Pytest can be learned later;
do not convert the tests automatically.

## Architecture

```text
Disease
  -> fetch + flatten trials                 registry.py        (done)
  -> group by drug, then phase              drug.py            (partial)
  -> per trial: trial_summary chain         router.py
       1. gather sources (no LLM): registry fields, registry references
          (RESULT / DERIVED), PubMed search by NCT ID
       2. grounded LLM summary of the gathered sources
       3. if nothing found: search agent (LangGraph) with PubMed free-text
          search + web search tools, max N tool calls
       + citation check on every output (router)
  -> per drug: drug summary from its trial summaries
  -> per disease: landscape + landscape.csv + Markdown dossiers
  -> evaluation harness
Observability: one log line per LLM call (tokens, latency, cost), all levels.
```

### Design decisions

- **Fixed chain, not multi-agent.** The router stays a deterministic handler
  chain in plain Python. Agents are handlers inside a chain: an "agentic
  workflow" that is predictable, testable and auditable.
- **Fixed retrieval first, agent only for the gaps.** Most trials can be
  handled with registry references + a PubMed search by NCT ID. The agent is
  for trials where that finds nothing (e.g. extension studies, trials only
  covered by press releases).
- **LangGraph only inside the agent handler.** The router does not use
  LangChain or LangGraph. `langchain-openai` may be used as the model wrapper.
- **Web search** is a tool of the agent. Cited URLs must have been fetched in
  this run, the same rule as for PMIDs.
- **Observability:** one JSON line per LLM call (timestamp, run_id, entity
  id, handler, model, input/output tokens, latency, cost). A
  homemade wrapper first. Kept separate from the summary records, linked by
  id + run_id.
- **Cache every fetch** (PubMed XML, web pages) on disk. Summaries are rerun
  often while tuning prompts; sources should not be refetched each time.
- **Dossier:** Markdown per drug, always rendered from saved summary records.
  Optional Streamlit demo later.
- **Docker:** after the CLI exists. Keys passed at runtime, never baked in.

### Open design questions (decide in Step A)

- **Schema.** `Evidence` was built for one short answer per trial. A trial
  summary needs more: a summary text with citations per claim, the stop
  category for stopped trials, and the list of sources used. Options: extend
  `Evidence` (e.g. `question="trial_summary"`), or new Pydantic models
  `TrialSummary`, `DrugSummary`, `Landscape`. Drug and disease summaries are
  not about one trial, so `nct_id` does not fit them.
- **How claims cite.** One source list per summary, or a source per sentence
  or claim? Per claim is easier to check, but harder to produce.
- **Which web search API** (and its cost and rate limits).
- **What a trial summary contains** for each status: stopped (why +
  category), completed (results), ongoing (status, enrolment, dates, primary
  endpoint).

## Current progress (as of 2026-11-18)

Done:
- **Registry** (`src/registry.py`): fetch with pagination, `flatten_study`
  (incl. `references` as `{"pmid", "type"}`), `is_drug_trial`. Output:
  `data/processed/amyotrophic_lateral_sclerosis_drug_trials.json`.
  146 of 402 ALS drug trials have references.
- **Evidence + router** (`src/evidence.py`, `src/router.py`): Pydantic
  `Source`, `Evidence`, `WhyStoppedLabel`; `run_chain` stops at the first
  `found`; chains for `status` and `why_stopped`.
- **Status handler** (`src/status_handler.py`) with a fallback.
- **Stop-reason classifier** (`src/why_stopped_handler.py`, prompt v2):
  structured output; `unclear` returns `not_found`. Batch run in
  `src/run_why_stopped.py` (resumable; delete its output file after a
  prompt change, or the old answers are kept).
  Hand labels for all 56 stopped ALS trials and an error analysis in
  `eval/`.
- **PubMed tools** (`src/pubmed.py`): `search_pubmed`, `fetch_abstract`,
  `parse_abstract_xml`; offline test on a saved XML response.

Partial:
- **Drug grouping** (`src/drug.py`): name normalisation, placebo excluded,
  `other_names` added. Missing: phase grouping, aliases, dose/salt. Not
  called by any pipeline yet; has a hard-coded absolute path.

Known issues:
- No `timeout` and no HTTP error handling in `urlopen` (registry and PubMed).
- `run_chain` returns the *last* handler's result when nothing is found, so
  an earlier handler's partial answer is lost.
- `pyproject.toml` still has the template name and description.
- Flat imports: scripts only run from inside `src/`. Moving to a package
  (`src/ctlandscape/`) is needed for the CLI and Docker.

Removed on 2026-11-18: the cookiecutter template files and `playground/`
(the first OpenAI toy scripts; still in git history).

## Next steps

Estimates are hours of focused work at this learning pace. Ranges are wide on
purpose.

| # | Work | Est. hours | Done when |
|---|---|---|---|
| 0 | **Clean start**: commit the cleanup on `wip` (incl. removal of handler versioning, 2026-11-18), fix the `pyproject.toml` name | 1 | All checks pass; clean `git status` |
| A | **Design the schema on paper**: answer the open design questions above; write the Pydantic models for the trial summary (drug and landscape can wait) | 2–3 | You can say what every field is for and who fills it in |
| B | **Gather sources for one trial, no LLM**: registry fields + `RESULT`/`DERIVED` references + PubMed search by NCT ID; timeout and HTTP error handling; disk cache for fetched abstracts | 4–6 | For 5 trials you can print every source with its PMID, and a second run makes no network calls |
| C | **Grounded trial summary**: an LLM handler that summarises *only* the gathered sources, cites each one, and returns `not_found` when the sources say nothing about the outcome. Reuse the stop classifier for stopped trials | 6–8 | 10 trials checked by eye: every claim traceable to its cited source |
| D | **Citation check in the router**: every cited PMID / URL must be in this run's fetched set, else `invalid_citation` | 2–3 | A fake PMID is caught |
| E | **Observability wrapper**: one place all LLM calls go through; JSONL log; price table | 2–4 | A batch run reports cost and latency per handler |
| F | **Tool calling, learned**: raw OpenAI tool-calling loop on a toy, then the same toy in LangGraph | 3–5 | You can draw the toy graph and explain what the model sees vs what your code runs |
| G | **Search agent**: second handler in the trial_summary chain; tools = PubMed free-text search + fetch, then web search + fetch; max N tool calls | 8–12 | 5 trials with no linked paper get a cited summary or `not_found` |
| H | **Drug grouping, finished**: phases (incl. `PHASE2\|PHASE3`), aliases, dose/salt; drug × phase table | 3–5 | 20 merges checked by hand |
| I | **Drug summary**: from trial summaries only, citing NCT IDs | 4–6 | 3 drugs checked: every claim traces to a trial summary |
| J | **Landscape + dossiers + landscape.csv** | 6–8 | One run produces all files for ALS |
| K | **Evaluation**: held-out sample labelled *before* seeing outputs; citation validity, faithfulness (is each claim supported by its source?), stop-category accuracy, cost per handler; fixed retrieval vs + agent; bootstrap CIs by drug; 3–5 failure cases | 10–14 | Results table with 95% CIs |
| L | **CLI + package layout, then Docker** | 4–6 | `docker run ... "ALS"` produces the landscape on a clean machine |
| M | **README + CV line** with real numbers | 3–4 | Someone else can clone, run and understand it in 10 minutes |

**Total: about 55–80 hours** (roughly 7–10 full days, or 6–8 weeks at ~10
hours a week).

**Milestone for the job application: 0 → E (about 17–25 hours).** That gives
a grounded, cited trial summary with a citation guardrail and cost logging.
Adding K on that slice (a small evaluation) makes the strongest story.

Cut order if time runs short: landscape polish → drug summary polish → web
search → agent tuning. **Never cut:** the citation check and evaluation.

### Design notes

- Registry reference types: `RESULT` and `DERIVED` are about this trial;
  `BACKGROUND` is sponsor context, not about this trial.
- REFALS: registry `DERIVED` PMID 34536404 matched the NCT ID PubMed search.
- Extension and rollover studies often have no paper of their own. The agent
  may need to find the parent study and cite its paper, saying clearly that
  the paper is about the parent.
- Search by NCT ID alone is not enough; the search tool should accept free
  text.
- Press releases are sponsor-written and may spin results; mark web sources
  clearly in the summary.
- Cost grows with every level (trials × articles × summaries), so measure
  it from the first LLM handler on.
- The stop-reason idea from Step 5 still applies: a `cause_stated: bool`
  field, with the rule enforced in code.

## Lessons so far

- Temperature does not make the model deterministic. Evaluate the saved
  output, not a fresh run.
- Handler versioning (`_v1`, `_v2`) was removed on 2026-11-18: handlers
  always use the latest prompt, and git keeps the history of the code. The
  `_v1`/`_v2` names in `eval/` and `data/interim/` are historical records of
  the Step 5 comparison. Before comparing two prompts again, save the first
  run's output under another name, so the second run does not overwrite it.
- Labelling all 56 trials made regressions visible: larger prompt rewrites
  fixed the targeted cases but broke others.
- Restart the Interactive window after editing a prompt (module caching).
- Test parsing on a saved response, not a live call.
- An assert that cannot fail tests nothing.
- Save the file before running it.

## Important files

- `src/registry.py`: ClinicalTrials.gov fetch and flattening
- `src/drug.py`: drug-name normalisation and grouping
- `src/evidence.py`: Pydantic `Source`, `Evidence`, `WhyStoppedLabel`
- `src/router.py`: handler chains
- `src/status_handler.py`: registry status handler and fallback
- `src/why_stopped_handler.py`: LLM stop-reason classifier and prompt
- `src/run_why_stopped.py`: resumable batch run
- `src/pubmed.py`: PubMed esearch / efetch and XML parser
- `src/explore_pubmed.py`: exploration of PubMed hits vs registry references
- `src/test_router.py`, `src/test_pubmed.py`, `src/test.py`: plain Python
  checks
- `eval/`: hand labels and error analysis
- `PLAN_1.md`: original learning plan (Downloads folder). Its Steps 7–10
  are replaced by the next steps above.

## Job application

- Roche Digital Technology, Data Scientist (AI Function, Warsaw or Poznań):
  enterprise AI, evaluation, guardrails, agentic workflows, cost.
- Describe the project as in progress.
- Do not quote accuracy figures: the hand labels were made on the same trials
  used for tuning.

## Safety reminders

- Do not commit `.env`.
- Do not put API keys in source code, notebooks, README files, or test output.
- Do not send sensitive data to an external model.
- Do not claim evidence without a source.
