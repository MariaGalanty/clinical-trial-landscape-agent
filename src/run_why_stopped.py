import json
from pathlib import Path
from tqdm import tqdm

from router import route_trial


if __name__ == "__main__":
    TRIAL_LIMIT = 2  # None for no limit

    # loads saved registery
    condition = "amyotrophic lateral sclerosis"
    project_root = Path(__file__).resolve().parent.parent
    processed_data_dir = project_root / "data" / "processed"
    input_data_path = (
        processed_data_dir / f"{'_'.join(condition.lower().split())}_drug_trials.json"
    )
    with open(input_data_path, encoding="utf-8") as f:
        trial_registry = json.load(f)

    # keep only the trials with why_stopped text
    stopped_trials = []
    for trial in trial_registry:
        if trial["why_stopped"]:
            stopped_trials.append(trial)
    trials_to_run = stopped_trials[:TRIAL_LIMIT]

    # calls route_trial(trial, "why_stopped") for each and prints progress (3/56 NCT...)
    classified_trials = []
    for trial in tqdm(trials_to_run, desc="Classifying why stopped", unit="trial"):
        evidence = route_trial(trial, "why_stopped")
        registry_fields = {
            "brief_title": trial["brief_title"],
            "overall_status": trial["overall_status"],
            "why_stopped": trial["why_stopped"],
        }
        record = {
            **registry_fields,
            **evidence.model_dump(),  # Evidence has .model_dump(), which turns it into a dict for json.dump.
        }
        classified_trials.append(record)
        tqdm.write(str(evidence.nct_id))

    # saves the results to data/interim/als_why_stopped.json.
    interim_data_dir = project_root / "data" / "interim"
    output_data_path = (
        interim_data_dir
        / f"{'_'.join(condition.lower().split())}_why_stopped_trials_classification.json"
    )

    with output_data_path.open("w", encoding="utf-8") as file:
        json.dump(classified_trials, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(classified_trials)} stopped drug trials to {output_data_path}")
