from typing import Any
import json
from pathlib import Path
from collections import defaultdict


def normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def is_placebo_intervention(intervention: dict[str, Any]) -> bool:
    name = normalize_name(intervention.get("name", ""))
    return "placebo" in name


def build_aliases(rows: list[dict[str, Any]]) -> dict[str, str]:
    groups: list[set[str]] = []
    other_name_counts: dict[str, int] = {}
    main_names: set[str] = set()

    for row in rows:
        for intervention in row.get("interventions", []):
            if intervention.get("type") != "DRUG":
                continue

            main_name = intervention.get("name")
            if not main_name:
                continue

            normalized_main = normalize_name(main_name)
            names = {normalized_main}
            main_names.add(normalized_main)

            for other_name in intervention.get("other_names", []):
                if other_name:
                    normalized_other = normalize_name(other_name)
                    names.add(normalized_other)
                    other_name_counts[normalized_other] = (
                        other_name_counts.get(normalized_other, 0) + 1
                    )

            groups.append(names)

    merged_groups: list[set[str]] = []

    for group in groups:
        overlapping_groups = [
            existing_group for existing_group in merged_groups if existing_group & group
        ]

        if not overlapping_groups:
            merged_groups.append(set(group))
            continue

        merged_group = set(group)

        for overlapping_group in overlapping_groups:
            merged_group.update(overlapping_group)
            merged_groups.remove(overlapping_group)

        merged_groups.append(merged_group)

    aliases: dict[str, str] = {}

    for group in merged_groups:
        shared_other_names = [
            name for name in group if other_name_counts.get(name, 0) > 1
        ]

        if shared_other_names:
            canonical_name = max(
                shared_other_names,
                key=lambda name: other_name_counts[name],
            )
        else:
            canonical_name = next(name for name in group if name in main_names)

        for name in group:
            if name != canonical_name:
                aliases[name] = canonical_name

    return aliases


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
