# Evaluation files

| File | What it is |
|---|---|
| `eval_split.json` | The frozen dev/test split: 40 ALS drug trials (15 dev, 25 test), sampled with a fixed seed. Do not regenerate. |
| `labels.csv` | Hand-made labels for these 40 trials: the "answer key" the pipeline is scored against. |

The labels were made **by hand, before looking at any pipeline output** for
these trials. The dev set is used while writing the prompt; the test set only
for the final numbers.

## `labels.csv`: one row per trial

Saved as CSV UTF-8. Lists inside one cell are separated by `;` (no spaces).
An empty cell means "none" or "not labelled".

| Column | Meaning | Example |
|---|---|---|
| `nct_id` | ClinicalTrials.gov ID | `NCT04569435` |
| `title` | Brief title from the registry | `Study of ANX005 in Adults With Amyotrophic Lateral Sclerosis (ALS)` |
| `split` | `dev` or `test` | `test` |
| `phase` | `phases` from the registry snapshot, joined with `/`, unchanged (`NA` = not applicable, `EARLY_PHASE1` = phase 0) | `PHASE2/PHASE3` |
| `status` | `overallStatus` from the registry snapshot, unchanged (see below) | `TERMINATED` |
| `paper_pmids_registry` | Every PMID the registry entry links (`RESULT`, `DERIVED`, `BACKGROUND`), kept as listed, **even when it is not about this trial**. Links that are not about the trial are explained in `notes`. | `28872918;28872914` |
| `paper_pmids_pubmed_google_scholar` | Papers about **this** trial (results, protocol, design, secondary analyses) found by searching PubMed and Google Scholar, and not already in `paper_pmids_registry`. Background papers and papers about other trials are left out. | `27589995` |
| `web_evidence` | 1–2 URLs that back the outcome when it is not in a paper from the two columns above (press release, news, conference abstract, journal page without a PMID). Evidence, not a complete list. | `https://example.com/press-release` |
| `outcome` | What is known about the trial's outcome: usually a quote from the abstract or source, or for stopped trials why it stopped. Empty if nothing was found. | `Did not meet its primary endpoint (ALSFRS-R at 24 weeks).` |
| `outcome_class` | `positive` / `negative` / `mixed` / `no_results` / `unknown`. Filled only where the outcome is known; empty otherwise (not needed for most metrics). | `negative` |
| `stop_category` | Stopped trials only (`TERMINATED`, `WITHDRAWN`, `SUSPENDED`): `efficacy_futility` / `safety` / `business_strategic` / `enrolment` / `other` / `unclear`. Same list as the summariser (`src/schemas.py`). Empty otherwise. | `business_strategic` |
| `notes` | Doubts and hard cases (extension study, shared acronym, conference abstract only, ...) | `Extension of NCT03127514` |
| `searched_on` | Date of the search (`YYYY-MM-DD`). Papers appear over time, so labels age. | `2026-11-23` |

### `status` values

As in ClinicalTrials.gov. The ones in this set:

| Status | Meaning |
|---|---|
| `COMPLETED` | Finished as planned |
| `TERMINATED` | Stopped early, after enrolling participants |
| `WITHDRAWN` | Stopped before enrolling anyone |
| `SUSPENDED` | Paused, may restart |
| `RECRUITING` | Ongoing, enrolling |
| `NOT_YET_RECRUITING` | Not started yet |
| `ACTIVE_NOT_RECRUITING` | Ongoing, enrolment closed |
| `UNKNOWN` | Not updated for 2+ years after the expected completion date. Many of these did finish; some have published results. |

### `outcome_class` values

| Value | Meaning |
|---|---|
| `positive` | Met its primary endpoint. For safety-only studies (most phase 1): no safety concerns found. |
| `negative` | Did not meet its primary endpoint, or stopped for futility/safety |
| `mixed` | Primary endpoint missed but other results reported as promising, or the reverse |
| `no_results` | Trial ended, but no outcome is public |
| `unknown` | Ongoing, or not known whether it ended |

## How the papers were searched

For each trial, in this order, in PubMed and Google Scholar:

1. **NCT ID**, e.g. `NCT04569435` (in Google Scholar with quotes).
2. **Trial acronym + ALS**, if the trial has one, e.g. `"PHOENIX" ALS`.
3. **Drug name + ALS**, with every name of the drug from the registry
   (code, generic, brand), e.g. `(ANX005 OR <generic name>) ALS`.

**Shortcut:** if the registry entry already links a paper (`RESULT` or
`DERIVED`) that, after reading it, really reports the results of this trial,
no further searches were done for that trial. For these trials
`paper_pmids` may therefore miss other papers about the trial (protocol,
secondary analyses); papers the pipeline finds beyond the label are checked
by hand at evaluation time.

Only the first page of results of each search was read (PubMed and Google
Scholar show 10 hits per page by default). If the first page had no paper
about this trial, the next pages were not searched; if it had one, the next
page was checked too.

Plus every reference listed in the registry entry. For each hit the
abstract was read by hand to decide (1) whether the paper is about this trial
(it then goes into `paper_pmids_pubmed_google_scholar`; registry links are
always kept in `paper_pmids_registry`) and (2) whether it reports the outcome
(used for `outcome` and `outcome_class`). When the abstract was not enough,
the full text was checked if free; otherwise the doubt is written in `notes`.

Web search (for `web_evidence`): Google, `NCT04569435 ALS`,
same first-page rule. For `TERMINATED` trials, also
`NCT04569435 ALS why terminated`, to find the reason for stopping
(used for `stop_category`).

A paper was counted as being about the trial only if its drug, phase, number
of participants, dates and sponsor match the registry entry.

## Computed by code, not stored

- **`paper_pmids`** = `paper_pmids_registry` + `paper_pmids_pubmed_google_scholar`.
  Because registry links are kept as listed, this can include background
  papers (see `notes`, e.g. NCT02405403, NCT06249867).
- **Fixed pipeline should find:** `found` if `paper_pmids` is not empty.
- **Agent should find:** `found` if there is only `web_evidence`;
  `not_found` if all three are empty.

## How the labels are used

| Metric | Compared | How |
|---|---|---|
| Paper recall | pipeline PMIDs vs `paper_pmids` | code |
| Wrong-trial rate | cited PMIDs not in `paper_pmids`, plus cited registry links that `notes` marks as background | code lists them, checked by hand |
| `not_found` correct | pipeline status vs "should find" | code |
| Stop category | summariser vs `stop_category` | code |
| Outcome correct | summary vs `outcome` (`yes` / `partly` / `no`) | by hand |
| Faithfulness | each claim vs the source it cites | by hand |
