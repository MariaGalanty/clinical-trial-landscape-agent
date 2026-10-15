from typing import Any
import json
from pathlib import Path
from collections import defaultdict


def normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def is_placebo_intervention(intervention: dict[str, Any]) -> bool:
    name = normalize_name(intervention.get("name", ""))
    return "placebo" in name


def get_drug_names(row: dict[str, Any]) -> set[str]:
    names = set()

    for intervention in row.get("interventions", []):
        if intervention.get("type") != "DRUG":
            continue

        if is_placebo_intervention(intervention):
            continue

        name = intervention.get("name")
        if name:
            names.add(normalize_name(name))

        for other_name in intervention.get("other_names", []):
            if other_name:
                normalized_other_name = normalize_name(other_name)
                if "placebo" not in normalized_other_name:
                    names.add(normalized_other_name)

    return names


def group_trials_by_drug(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:

    groups = defaultdict(list)

    for row in rows:
        for drug_name in get_drug_names(row):
            groups[drug_name].append(row)

    return dict(groups)


if __name__ == "__main__":
    assert normalize_name(" Pirfenidone ") == "pirfenidone"
    assert normalize_name("PIRFENIDONE") == "pirfenidone"
    assert normalize_name("pirfenidone   ") == "pirfenidone"

    file_path = Path(
        r"C:\Users\mgalant\Documents\Python Projects\clinical-trial-landscape-agent"
        r"\data\processed\amyotrophic_lateral_sclerosis_drug_trials.json"
    )

    with file_path.open("r", encoding="utf-8") as file:
        rows: list[dict[str, Any]] = json.load(file)

    grouped = group_trials_by_drug(rows)

    print(f"Number of drug groups: {len(grouped)}")

    for drug_name, drug_rows in grouped.items():
        print(f"{drug_name}: {len(drug_rows)} trial(s)")
