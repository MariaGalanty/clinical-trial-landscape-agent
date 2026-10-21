# Error analysis: why_stopped LLM classifier

This document records where the `why_stopped` classifier disagreed with my
hand labels, why I think it failed, and what I changed in the prompt.

## 1. Setup

| | |
|---|---|
| Handler | `why_stopped_llm_v1` and `why_stopped_llm_v2` ([src/why_stopped_handler.py](../src/why_stopped_handler.py)) |
| Model | `gpt-5.4-nano` (OpenAI Responses API, structured output), the same for both versions |
| Input | `why_stopped` free text from ClinicalTrials.gov, nothing else |
| Data | 56 ALS drug trials with a non-empty `why_stopped` |
| Output v1 | [amyotrophic_lateral_sclerosis_why_stopped_trials_classification_v1.json](../data/interim/amyotrophic_lateral_sclerosis_why_stopped_trials_classification_v1.json) |
| Output v2 | [amyotrophic_lateral_sclerosis_why_stopped_trials_classification_v2.json](../data/interim/amyotrophic_lateral_sclerosis_why_stopped_trials_classification_v2.json) |
| Hand labels | [why_stopped_analysis_v1.csv](why_stopped_analysis_v1.csv) (all 56 trials) |
| Date | 2026-10-21 |

Categories: `efficacy_futility`, `safety`, `business_strategic`, `enrolment`,
`other`, `unclear`. `unclear` returns status `not_found`, so the trial is passed
on to the next handler in the chain (the PubMed agent, Step 7).

### How the trials were reviewed

- I gave my own category from the `why_stopped` text **before** looking at
  the model's answer.
- I've evaluated all 56 trials

## 2. Results for v1

**Agreement with my labels: 50 out of 56 trials (89%).**

Category counts for all 56 trials: `efficacy_futility` 21, `unclear` 16,
`business_strategic` 6, `enrolment` 5, `other` 5, `safety` 3.

### Agreements

| NCT ID | `why_stopped` (shortened) | Label | Why it is a useful case |
|---|---|---|---|
| NCT03948178 | Open-label extension of REFALS (NCT03505021); REFALS showed lack of efficacy, so sponsor stopped this study | `efficacy_futility` | Upstream study **with** its reason stated: the model followed the chain to the root cause |
| NCT00982150 | Core study unsuccessful | `unclear` | Upstream study **without** its reason: the model did not guess efficacy |
| NCT04948645 | Company Decision | `unclear` | Bare sponsor decision, handled correctly (compare with NCT05949294 below) |
| NCT05053035 | Sponsor is considering a subsequent study, maybe with different eligibility criteria | `unclear` | Plans for the future, not a reason for stopping |
| NCT04326283 | Necessary data have been collected | `other` | A neutral reason that is stated, not a failure |

### Disagreements

| NCT ID | `why_stopped` (shortened) | My label | Model | Model status | Pattern |
|---|---|---|---|---|---|
| NCT05949294 | Company business decision | `unclear` | `business_strategic` | found | A |
| NCT03457753 | Sponsor stopped the study due to a change in study plans | `unclear` | `business_strategic` | found | A |
| NCT01999803 | Issues with supply of infusion system. Lack of favorable benefit-risk ratio in sNN0029-003 (interim data) | `efficacy_futility` | `other` | found | C |
| NCT02269436 | Same text as NCT01999803 | `efficacy_futility` | `other` | found | C |
| NCT03705390 | Suspended due to COVID-19, treatment stopped, never reopened to recruitment | `other` | `unclear` | not_found | B |
| NCT06903286 | Patients treated through compassionate use program | `other` | `unclear` | not_found | not grouped |

NCT06903286 is still open: one could also argue `unclear`, because the text
says what happened to the patients, not why the trial stopped.

**Same text, different labels.** NCT01999803, NCT02269436 and NCT01384162 have
the same `why_stopped` text. v1 labelled the first two `other` and the third
`efficacy_futility`. So some disagreements come from run-to-run variation in
the model, not only from the prompt.

## 3. Failure patterns

### A: Reads a reason into sponsor wording (2 cases)

The prompt already has the rule *"A bare sponsor, funder, or business decision
with no stated reason is unclear."* The model applied it to "Company Decision"
(NCT04948645) but not to **"Company business decision"** (NCT05949294). The
only difference is the word *business*, which matches the category name
`business_strategic`.

The model's own explanation contradicts its label:

> "…stopped due to a company/business decision **without specifying** a
> safety, efficacy, or recruitment cause." → `business_strategic`

NCT03457753 ("change in study plans") has the same problem: the explanation
says no cause is given, and the label still says `business_strategic`.

**Likely cause:** the model matches words to category names instead of
checking whether the text gives a cause.

### B: Event outside the trial's control seen as no reason (1 case)

For COVID-19, the model correctly saw that recruitment problems did not cause
the stop, so it did not choose `enrolment`. Then it chose `unclear` instead of
`other`. The prompt says nothing about events outside the trial's control
(pandemic, disaster, war).

**Likely cause:** a gap in the prompt. The root-cause rule exists, but nothing
says which category an outside event belongs to.

### C: "Unfavourable benefit-risk" not seen as efficacy (2 cases, same text)

The model found both reasons (supply problem and unfavourable benefit-risk on
interim data) and chose `other`. The tie-break order (safety →
efficacy_futility → enrolment → business_strategic → other) should have chosen
`efficacy_futility`. So the order was probably applied correctly, and the
model simply did not read "lack of favorable benefit-risk ratio" as an
efficacy reason.

**Likely cause:** "benefit-risk" is not linked to any category in the prompt.
A third trial with the same text was labelled correctly, so this may also be
run-to-run variation.

## 4. Prompt changes for v2

v2 keeps the v1 prompt and adds two short rules at the end of the rule list:

```text
- Events outside the trial's control, such as a pandemic, are other.
- "Business decision", "Company decision" or "Sponsor decision" with no reason given is unclear.
```

| Rule | Targets | Why |
|---|---|---|
| Outside events → other | B | Fills the gap: the prompt had no category for events outside the trial's control |
| Bare decisions → unclear | A | v1's rule was abstract ("a bare … decision"). The new rule names the exact phrases, including the word "business" |

Pattern C has no new rule. Benefit-risk wording is ambiguous (it can mean too
little benefit or too much risk), so I want to decide how to label it first
(see next steps).

I kept the change small on purpose. Larger rewrites of several rules at once
fixed the targeted cases but broke others, and it was not possible to tell
which rule caused which change.

### Full prompt v1

<details>
<summary>v1 instructions (commit 488fa81)</summary>

```text
You classify why a clinical trial was stopped, using the "why stopped"
text from its ClinicalTrials.gov registry record.

Categories:
- efficacy_futility: the treatment did not work, or an analysis showed it was unlikely to work
- safety: adverse events, toxicity, or other safety concerns
- business_strategic: funding, sponsor or company strategy, acquisition, regulatory, or commercial reasons
- enrolment: difficulty recruiting or retaining enough participants
- other: a specific, stated reason that fits none of the above (e.g. drug supply problems, PI left the institution)
- unclear: no real reason is given, or the text is too vague to classify

Rules:
- Use only the given text. Do not guess using outside knowledge about the drug or sponsor.
- Classify the root cause, not its consequences. "Terminated by sponsor due to slow recruitment"
  is enrolment, because the sponsor decision was caused by recruitment.
- If several independent reasons are given, choose the first one that applies in this order:
  safety, efficacy_futility, enrolment, business_strategic, other.
- A bare sponsor, funder, or business decision with no stated reason is unclear.
- Phrases like "no recruitment" or "no data collected" describe the result of stopping early.
  They are not enrolment unless the text says recruitment problems caused the stop.
  Example: "Terminated by funder before recruitment started, no patients enrolled" is unclear,
  because the funder's reason is not stated.
```

</details>

### Full prompt v2

<details>
<summary>v2 instructions</summary>

```text
You classify why a clinical trial was stopped, using the "why stopped"
text from its ClinicalTrials.gov registry record.

Categories:
- efficacy_futility: the treatment did not work, or an analysis showed it was unlikely to work
- safety: adverse events, toxicity, or other safety concerns
- business_strategic: funding, sponsor or company strategy, acquisition, regulatory, or commercial reasons
- enrolment: difficulty recruiting or retaining enough participants
- other: a specific, stated reason that fits none of the above (e.g. drug supply problems, PI left the institution)
- unclear: no real reason is given, or the text is too vague to classify

Rules:
- Use only the given text. Do not guess using outside knowledge about the drug or sponsor.
- Classify the root cause, not its consequences. "Terminated by sponsor due to slow recruitment"
  is enrolment, because the sponsor decision was caused by recruitment.
- If several independent reasons are given, choose the first one that applies in this order:
  safety, efficacy_futility, enrolment, business_strategic, other.
- A bare sponsor, funder, or business decision with no stated reason is unclear.
- Phrases like "no recruitment" or "no data collected" describe the result of stopping early.
  They are not enrolment unless the text says recruitment problems caused the stop.
  Example: "Terminated by funder before recruitment started, no patients enrolled" is unclear,
  because the funder's reason is not stated.
- Events outside the trial's control, such as a pandemic, are other.
- "Business decision", "Company decision" or "Sponsor decision" with no reason given is unclear.
```

</details>

## 5. Results for v2

**Agreement with my labels: 52 out of 56 trials (93%), compared with 50 for v1.**

| | Mine | v1 | v2 |
|---|---|---|---|
| Agreement with my labels | | 50/56 | **52/56** |
| `efficacy_futility` | 23 | 21 | 23 |
| `unclear` | 16 | 16 | 16 |
| `business_strategic` | 4 | 6 | 5 |
| `enrolment` | 5 | 5 | 5 |
| `other` | 5 | 5 | 4 |
| `safety` | 3 | 3 | 3 |

**Compared with v1:**

| | NCT ID | `why_stopped` | My label | v1 | v2 |
|---|---|---|---|---|---|
| Fixed | NCT05949294 | Company business decision | `unclear` | `business_strategic` | `unclear` ✅ |
| Fixed | NCT03705390 | COVID-19 suspension | `other` | `unclear` | `other` ✅ |
| Fixed | NCT01999803 | Supply issues + unfavourable benefit-risk | `efficacy_futility` | `other` | `efficacy_futility` ✅ |
| Fixed | NCT02269436 | Same text as NCT01999803 | `efficacy_futility` | `other` | `efficacy_futility` ✅ |
| Broken | NCT06215755 | Terminated by Sponsor due to lack of risk-benefit data | `safety` | `safety` | `efficacy_futility` |
| Broken | NCT04066244 | Study terminated after assessment of potential benefit-risk from available data | `efficacy_futility` | `efficacy_futility` | `safety` |
| Wrong in both | NCT03457753 | The Sponsor stopped the study due to a change in study plans | `unclear` | `business_strategic` | `business_strategic` |
| Wrong in both | NCT06903286 | Patients treated through compassionate use program | `other` | `unclear` | `unclear` |

### What this shows

- **The two new rules work for the cases they target.** "Company business
  decision" and COVID-19 are both correct.
- **The benefit-risk cases (NCT01999803, NCT02269436) are probably fixed by
  chance.** v2 has no benefit-risk rule, and a third trial with the same text
  was already right in v1.
- **Benefit-risk wording is the least stable area.** Both new errors are
  benefit-risk texts, and the label moves between `safety` and
  `efficacy_futility`. "Benefit-risk" really is ambiguous, so this is partly
  a labelling question, not only a model error. 
- **"Change in study plans" is wrong in both versions,** and the model's
  answer again says that no specific reason is given. This is the most stable
  error.

### Is v2 better than v1?

52 vs 50 is a difference of 2 trials. In a repeated run with an unchanged
prompt, 4 of 56 labels changed, so a difference of 2 is **within run-to-run
noise**. What speaks for v2: it is a small change from v1, each change is
explained, and the two rules fixed exactly the cases they target. For two broken trials the change is from saety to efficacy_futility and Iw oudl say both ould work in this context, so I will stay with v2. 
