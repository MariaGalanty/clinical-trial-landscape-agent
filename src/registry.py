"""Learner's workspace for the ClinicalTrials.gov API exercises."""

# from urllib.request import urlopen
import urllib.request
import json

from urllib.parse import urlencode
from typing import Any


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
        raw_body = response.read()  # read raw bytes from the response
        json_text = raw_body.decode(
            "utf-8"
        )  # decodes the raw bytes into readible utf-8
        data = json.loads(json_text)  # parse the JSON data into a Python dictionary
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
        all_studies.extend(page["studies"])
        if max_studies is not None and len(all_studies) >= max_studies:
            return all_studies[:max_studies]
        next_page_token = page.get("nextPageToken")
        page_token = next_page_token
        if not next_page_token:
            break
    return all_studies


if __name__ == "__main__":
    condition = "amyotrophic lateral sclerosis"
    all_studies = fetch_all_studies(condition, page_size=3, max_studies=7)
    print(f"Fetched studies: {len(all_studies)}")
