import json
import random
from pathlib import Path
from pubmed import search_pubmed, fetch_abstract

if __name__ == "__main__":
    # Read the json with stoppped trials
    project_root = Path(__file__).resolve().parent.parent
    data_path = (
        project_root / "data/processed/amyotrophic_lateral_sclerosis_drug_trials.json"
    )
    print(data_path)
    with open(data_path, encoding="utf-8") as f:
        drug_trials_registery = json.load(f)

    nct_id_values = [
        registery["nct_id"]
        for registery in drug_trials_registery
        if "nct_id" in registery
    ]
    nct_id_values_with_references = [
        registery["nct_id"]
        for registery in drug_trials_registery
        if "nct_id" in registery and registery.get("references", []) != []
    ]
    print(len(nct_id_values_with_references))

    trials = [
        {
            "nct_id": registery.get("nct_id"),
            "brief_title": registery.get("brief_title"),
            "references": registery.get("references", []),
        }
        for registery in drug_trials_registery
        if "nct_id" in registery
    ]

    # search the articles for the articles related to NCT ID
    counter = 0
    for trial in trials:
        matched_pmids = search_pubmed(trial["nct_id"])
        if matched_pmids != []:
            counter += 1
            print(f"NCT ID: {trial['nct_id']}")
            print(f"Brief title: {trial['brief_title']}")
            print(f"PubMed search: {matched_pmids}")
            print(f"Registry references: {trial['references']}")
            for pmid in matched_pmids:
                pmid_abstract = fetch_abstract(pmid)
                for key_pmid, value_pmid in pmid_abstract.items():
                    print(f"{key_pmid}: {value_pmid}")
        if counter == 5:
            break


# print their titles

# search the pubmed for the articles related to NCT ID

# print titles
