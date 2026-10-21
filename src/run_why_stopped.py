import json
from pathlib import Path
from tqdm import tqdm

from router import route_trial
from why_stopped_handler import WHY_STOPPED_LLM_VERSION


if __name__ == "__main__":
    TRIAL_LIMIT = 3  # None for no limit

    # loads saved registery
    condition = "amyotrophic lateral sclerosis"
    project_root = Path(__file__).resolve().parent.parent
    processed_data_dir = project_root / "data" / "processed"
    input_data_path = (
        processed_data_dir / f"{'_'.join(condition.lower().split())}_drug_trials.json"
    )
    with open(input_data_path, encoding="utf-8") as f:
        trial_registry = json.load(f)

    interim_data_dir = project_root / "data" / "interim"
    output_data_path = (
        interim_data_dir
        / f"{'_'.join(condition.lower().split())}_why_stopped_trials_classification_{WHY_STOPPED_LLM_VERSION}.json"
    )

    # keep only the trials with why_stopped text
    stopped_trials = []
    for trial in trial_registry:
        if trial["why_stopped"]:
            stopped_trials.append(trial)
    trials_to_run = stopped_trials[:TRIAL_LIMIT]

    if output_data_path.is_file():
        with open(output_data_path, encoding="utf-8") as f:
            classified_trials = json.load(f)
            nct_id_saved_trials = {trial["nct_id"] for trial in classified_trials}
    else:
        classified_trials = []
        nct_id_saved_trials = set()

    for trial in tqdm(trials_to_run, desc="Classifying why stopped", unit="trial"):
        if trial["nct_id"] in nct_id_saved_trials:
            continue
        try:
            evidence = route_trial(trial, "why_stopped")
        except Exception as e:
            print(f"Calling API for the trial {trial['nct_id']} has failed: {e}")
            continue
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
        with output_data_path.open("w", encoding="utf-8") as file:
            json.dump(classified_trials, file, indent=2, ensure_ascii=False)
        tqdm.write(str(evidence.nct_id))

    print(f"Saved {len(classified_trials)} stopped drug trials to {output_data_path}")
