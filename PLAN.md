# Plan: clinical trial landscape agent

Branch `restart`, written 2026-11-18. This file is the single source of truth
for the project. Notes from the first version are in `docs/archive/`.

## 1. Goal

**Input:** a disease name (first: ALS).

**Output:**
- one **trial summary** per drug trial: what is known about its outcome, as
  short sentences, each citing its source (registry field, PMID or URL);
- **`landscape.csv`**: one row per trial (drug names, phase, status,
  enrolment, dates, summary status, number of sources);
- **`landscape.md`**: the trials as a readable report, grouped by status and
  phase, with each trial's cited summary.

**Golden rule:** every claim cites a source that was fetched in this run.
Otherwise the answer is `not_found`. A wrong `found` is worse than an honest
`not_found`.

## 2. Scope

**In:**
- registry facts, papers linked in the registry, PubMed search;
- a grounded LLM summariser;
- a search agent (LangGraph) with PubMed free-text search and web search, for
  trials where the fixed search finds nothing;
- a citation check on every output;
- a cost and latency log;
- an evaluation of the summariser and of the agent.

**Out (for now):**
- grouping trials by drug and per-drug summaries (the CSV lists drug names per
  trial, so a reader can sort or filter by drug);
- an LLM-written disease summary;
- other diseases (the code takes the disease as a parameter, but only ALS is
  run and checked);
- a web app.

## 3. Pipeline

```text
disease
  -> fetch all trials, save the raw snapshot (query + date)        [code]
  -> flatten + filter: keep trials with a real drug intervention   [code]
  -> per trial, a chain that stops at the first "found":
       1. gather sources                                           [code]
          registry facts; RESULT/DERIVED references;
          PubMed: NCT ID, then acronym
       2. summariser: cited sentences from these sources only      [LLM]
       3. if not_found: search agent                               [agent]
          tools: PubMed free-text search, fetch abstract,
                 web search, fetch page; max 5 tool calls
       + citation check after each step                            [code]
  -> landscape.csv + landscape.md                                  [code]
every LLM call -> one line in the cost and latency log
```

Design rules:
- **Fixed chain, not multi-agent.** The chain is plain Python. LangGraph is
  used only inside the agent handler.
- **One record for every handler:** each step returns a `TrialSummary` (see
  section 4), so steps can be added or reordered.
- **Cache every fetch** (PubMed XML, web pages) on disk. Summaries are rerun
  often; sources should not be refetched.
- **Templates, not LLMs, write the Markdown and CSV.**

## 4. Data models (Pydantic)

`Source`: `kind` (`registry` | `pubmed` | `web`), `reference` (field name,
PMID or URL), `title`.

`Claim`: `text` (one sentence), `topic` (`stop_reason` | `results` |
`progress` | `design`), `sources` (at least one `Source`).

`TrialSummary`:

| Field | Filled by |
|---|---|
| `nct_id`, `brief_title`, `acronym`, `interventions`, `phases`, `overall_status`, `enrollment_count`, `start_date`, `completion_date`, `primary_endpoint`, `has_results`, `why_stopped_text` | registry, no LLM |
| `stop_category` (`None` unless stopped) | summariser |
| `claims: list[Claim]` | summariser or agent |
| `sources_fetched: list[Source]` | source gathering and agent |
| `status`: `found` / `not_found` / `invalid_citation` | citation check |
| `handler`, `n_tool_calls`, `searched_at`, `run_id` | the step that ran |

`found` means: at least one claim from a paper or web page that passed the
citation check. Registry facts alone do not make a trial `found`.

## 5. Evaluation

Two separate questions, measured separately.

### 5a. Fixed pipeline (sources + summariser)

**Labelled set:** about 40 trials, sampled per status (stopped, completed,
ongoing), with a few known hard cases. Split before looking at any output:
- **dev (about 15):** used while writing and tuning the prompt;
- **test (about 25):** used only for the final numbers.

**Labels, made by hand before seeing outputs:** for each trial, which papers
are really about this trial (found by searching yourself), and a one-line
"what is known about the outcome".

**Metrics:**

| Metric | How | Target |
|---|---|---|
| Citation validity | automatic: every cited source was fetched in this run | 100 % (it is a guardrail) |
| Paper recall | share of the labelled papers that the pipeline found | report |
| Wrong-trial rate | share of cited papers that are about another trial | as low as possible |
| Faithfulness | per claim, by hand: does the cited source say this? | report |
| Outcome correct | summary agrees with the hand label | report |
| `not_found` correct | `not_found` trials really have no paper | report |
| Cost, latency | from the log, per trial and per handler | report |

Report each with a 95 % bootstrap confidence interval over trials.

### 5b. Agent

The agent only runs on trials the fixed pipeline left `not_found`, so it is
measured on its own terms, not against the fixed pipeline.

**Set:** all trials that are `not_found` after the fixed pipeline (or a sample
of about 25 if there are many). Check by hand, after the run, every trial the
agent marked `found`.

| Metric | Meaning |
|---|---|
| Recovery rate | share of `not_found` trials the agent turned into `found` |
| Precision of recovered | share of those that are correct: right trial, and every claim supported by its source |
| Wrong-trial rate | recovered answers that describe a different trial |
| Web share | share of recovered answers that rely on web sources only (weaker evidence) |
| Cost per recovered trial | total agent cost / number of correct recoveries |
| Tool calls | average, and how often the 5-call limit was hit |

Plus the citation check on the agent's output (must be 100 %) and one test
with a fabricated PMID, which must come back `invalid_citation`.

### 5c. Error analysis

3 to 5 documented failures per handler: what went wrong, why, and what would
fix it.

**Never quote numbers from the dev set.** Only the test-set numbers go into
the README or a CV.

## 6. Steps

Each step ends with a "done when" check. Days are focused working days.

| # | Step | Done when | Days |
|---|---|---|---|
| 1 | **Registry, revisited.** Save the raw snapshot (query + date); add `acronym` and `primary_endpoint` to `flatten_study`; better drug filter (non-placebo; decide `DRUG` / `BIOLOGICAL` / `GENETIC`); timeout; disease as a parameter | Counts per filter rule; 10 removed and 10 kept trials checked by eye | 0.5 |
| 2 | **Models** in `models.py`: `Source`, `Claim`, `TrialSummary` | A hand-made record validates; a claim with no source fails | 0.25 |
| 3 | **Gather sources**, no LLM: references, PubMed by NCT ID, then acronym; timeout + error handling; disk cache | For 5 trials every source is printed; a second run makes no network calls | 0.5 |
| 4 | **Label the evaluation set** (dev + test), before any summariser exists | 40 trials labelled; split saved | 1 |
| 5 | **Summariser + citation check + cost log** | 10 dev trials checked by eye; a fake PMID is caught; cost per trial known | 1 |
| 6 | **Full run of the fixed pipeline** + `landscape.csv` + `landscape.md` | One command produces both files for ALS | 0.5 |
| 7 | **Evaluate the fixed pipeline** (5a) | Metrics table with CIs on the test set; 3 to 5 failures written up | 0.5 |
| 8 | **Search agent** (LangGraph): PubMed free text + fetch, then web search + fetch; max 5 tool calls; second step in the chain | 5 `not_found` dev trials give a cited answer or `not_found` | 1–1.5 |
| 9 | **Evaluate the agent** (5b) | Agent metrics table; failures written up | 0.5 |
| 10 | **README, CLI, Docker, CV line** | Someone else can clone, run and understand it in 10 minutes | 0.5–1 |

**Total: about 6–7 days.** Steps 1–3 and 5–6 are the two-day "working
pipeline". Steps 4, 7 and 9 make it credible. Step 4 comes before step 5 on
purpose: labels made after seeing outputs are biased toward the outputs.

If time runs short, cut in this order: Docker → `landscape.md` polish → web
search (keep the agent with PubMed only). **Never cut:** the citation check
and the evaluation.

## 7. Open decisions

- Which intervention types count as a drug (`DRUG` only, or also
  `BIOLOGICAL` and `GENETIC`)? Decide from the counts in step 1.
- What counts as placebo-like (placebo, sham, vehicle, saline, standard of
  care)? Decide from real names in step 1.
- Which web search API (cost, rate limits, terms of use)? Decide before
  step 8.
- When a paper describes a parent study (extension trials), may the summary
  cite it? Proposal: yes, with a claim that says so explicitly.

## 8. Reused from the first version

- `src/registry.py`, `src/pubmed.py`, `src/test_pubmed.py`: kept.
- `src/drug.py`: `is_placebo_intervention` moves into the filter; grouping is
  out of scope.
- From branch `wip` if useful: the stop-reason prompt (for
  `stop_category`) and the router's `run_chain` idea.
