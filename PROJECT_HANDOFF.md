# Project Handoff

## Project

Clinical-trial landscape agent: a Python project that fetches and groups
ClinicalTrials.gov studies, then uses evidence-grounded handlers and an LLM
to analyze trial stop reasons.

The intended first agent is a modular, explainable prototype:

```text
trial data
    -> router
    -> registry handler
    -> PubMed tool/agent when needed
    -> LLM classification
    -> validated Evidence with citations
```

The model provider should remain replaceable. We plan to use OpenAI first, but
the design should later allow Ollama, Hugging Face, or another local model.

## Learning agreement

This is a learning project. The assistant should:

- explain concepts before implementation;
- use small toy examples unrelated to the project;
- give the learner a focused task;
- avoid writing whole files or features unless explicitly requested;
- review learner-written code for bugs first, then readability;
- ask check-your-understanding questions before moving to the next concept;
- use Pylance/runtime checks and explain what they show.

The learner currently prefers plain Python test scripts. Pytest can be learned
later; do not convert the tests automatically.

## Current progress

- Registry API fetching and pagination exist in `src/registry.py`.
- Registry records are flattened into trial dictionaries.
- Basic drug grouping exists in `src/drug.py`.
- Basic grouping currently uses normalized registry intervention names and
  excludes placebo interventions.
- Drug aliases, dose/salt normalization, phase grouping, and advanced
  combination handling are intentionally postponed.
- Pydantic is installed and used in `src/evidence.py`.
- `Source` and `Evidence` models exist.
- `handle_status` exists in `src/status_handler.py`.
- `handle_status_fallback` exists in the same file.
- `route_trial` exists in `src/router.py`.
- The router has a status handler chain:
  `handle_status -> handle_status_fallback`.
- Manual checks are in `src/test.py`.
- The manual test script and Pylance checks passed at the end of the last
  session.

## Current architecture

```text
trial dictionary
    -> route_trial(trial, "status")
    -> status handler chain
    -> Evidence
```

`Evidence` fields:

```text
nct_id
question
answer
category
sources
status
handler
n_tool_calls
```

`category` is relevant to `why_stopped`; for `status` and `results`, it is
normally `None`.

## Important current files

- `src/registry.py`: ClinicalTrials.gov fetch and flattening
- `src/drug.py`: basic drug-name normalization and grouping
- `src/evidence.py`: Pydantic `Source` and `Evidence`
- `src/status_handler.py`: registry status handler and fallback
- `src/router.py`: status routing and handler chain
- `src/test.py`: current plain Python checks
- `PLAN_1.md`: original learning plan, located in the Downloads folder

## Next session: recommended order

1. Review the router chain once more and explain why it stops at the first
   `"found"` result.
2. Learn one minimal OpenAI API call in a separate playground file.
3. Add the OpenAI dependency only when the learner is ready and has an API
   account/key.
4. Keep the key only in a local `.env` file; never commit or paste it.
5. Start with a toy classification prompt, not real project data.
6. Move from free text to validated structured JSON.
7. Build a `why_stopped` registry LLM handler that returns `Evidence`.
8. Add PubMed tools and then the agent fallback.
9. Add citation validation before calling the first agent complete.
10. Prepare a portfolio README and push to GitHub. Docker is optional, not
    required for the portfolio version.

## First-agent definition of done

A first local prototype is complete when one trial can be processed as follows:

```text
registry why_stopped text
    -> LLM classification
    -> Evidence(category=..., status="found")
```

The stronger version additionally searches PubMed when the registry reason is
vague, cites only fetched evidence, and returns `not_found` when evidence is
insufficient.

## Safety reminders

- Do not commit `.env`.
- Do not put API keys in source code, notebooks, README files, or test output.
- Do not send sensitive data to an external model.
- Do not claim evidence without a source.
