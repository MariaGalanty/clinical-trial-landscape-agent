"""Learner's workspace for the ClinicalTrials.gov API exercises."""

# from urllib.request import urlopen
import urllib.request
import json

from urllib.parse import urlencode
from typing import Any
from pathlib import Path


def fetch_one_page(
    condition: str, page_size: int = 3, page_token: str | None = None
) -> dict[str, Any]:
    """Fetch one page of matching studies"""
    if not condition.strip():
        raise ValueError("condition must not be empty")

    parameters = {
        "query.cond": condition,
        "pageSize": page_size,
        "countTotal": "true",
    }

    if page_token is not None:
        parameters["pageToken"] = page_token

    query_string = urlencode(parameters)
    url_path = f"https://clinicaltrials.gov/api/v2/studies?{query_string}"

    with urllib.request.urlopen(url_path) as response:
        data = json.load(response)
        return data


def fetch_all_studies(
    condition: str,
    page_size: int = 100,
    max_studies: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch all pages of matching studies"""
    all_studies = []
    page_token = None
    page_number = 0
    while True:
        page_number += 1
        print(f"Fetching page {page_number}")
        page = fetch_one_page(condition, page_size=page_size, page_token=page_token)
        all_studies.extend(page["studies"])
        if max_studies is not None and len(all_studies) >= max_studies:
            return all_studies[:max_studies]
        next_page_token = page.get("nextPageToken")
        page_token = next_page_token
        if not next_page_token:
            break

    return all_studies


def flatten_study(study: dict[str, Any]) -> dict[str, Any]:
    """Flatten a study dictionary and select only the fields we are interested in."""
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    interventions_module = protocol.get("armsInterventionsModule", {})
    raw_interventions = interventions_module.get("interventions", [])

    interventions = []

    for intervention in raw_interventions:
        interventions.append(
            {
                "type": intervention.get("type"),
                "name": intervention.get("name"),
                "other_names": intervention.get("otherNames", []),
            }
        )

    row = {
        "nct_id": identification.get("nctId"),
        "organization": identification.get("organization", {}).get("fullName"),
        "brief_title": identification.get("briefTitle"),
        "official_title": identification.get("officialTitle"),
        "overall_status": status.get("overallStatus"),
        "why_stopped": status.get("whyStopped"),
        "has_expanded_access": status.get("expandedAccessInfo", {}).get(
            "hasExpandedAccess"
        ),
        "start_date": status.get("startDateStruct", {}).get("date"),
        "start_date_type": status.get("startDateStruct", {}).get("type"),
        "primary_completion_date": status.get("primaryCompletionDateStruct", {}).get(
            "date"
        ),
        "primary_completion_date_type": status.get(
            "primaryCompletionDateStruct", {}
        ).get("type"),
        "completion_date": status.get("completionDateStruct", {}).get("date"),
        "completion_date_type": status.get("completionDateStruct", {}).get("type"),
        "brief_summary": protocol.get("descriptionModule", {}).get("briefSummary"),
        "conditions": protocol.get("conditionsModule", {}).get("conditions", []),
        "study_type": design.get("studyType"),
        "phases": design.get("phases", []),
        "time_perspective": design.get("designInfo", {}).get("timePerspective"),
        "enrollment_count": design.get("enrollmentInfo", {}).get("count"),
        "enrollment_type": design.get("enrollmentInfo", {}).get("type"),
        "interventions": interventions,
        "eligibility_criteria": eligibility.get("eligibilityCriteria"),
        "healthy_volunteers": eligibility.get("healthyVolunteers"),
        "sex": eligibility.get("sex"),
        "standard_ages": eligibility.get("stdAges", []),
        "study_population": eligibility.get("studyPopulation"),
        "sampling_method": eligibility.get("samplingMethod"),
        "locations": protocol.get("contactsLocationsModule", {}).get("locations", []),
        "has_results": study.get("hasResults", False),
        "linked_pmids": [],  # PubMed identifier
    }

    return row


def is_drug_trial(row) -> bool:
    return any(
        intervention.get("type") == "DRUG"
        for intervention in row.get("interventions", [])
    )


if __name__ == "__main__":
    condition = "amyotrophic lateral sclerosis"
    project_root = Path(__file__).resolve().parent.parent

    all_studies = fetch_all_studies(condition)
    rows = [flatten_study(study) for study in all_studies]
    drug_rows = [row for row in rows if is_drug_trial(row)]
    print(f"All trials: {len(rows)}")
    print(f"Drug trials: {len(drug_rows)}")

    output_data_dir = project_root / "data" / "processed"
    output_data_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(
        output_data_dir / f"{'_'.join(condition.lower().split())}_drug_trials.json"
    )
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(drug_rows, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(drug_rows)} drug trials to {output_path}")

    # Grouping trails by drug and phase number, adding also overall status
    # drug_rows
