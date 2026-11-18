import os
import json
import time
import xml.etree.ElementTree as ET

from dotenv import load_dotenv, find_dotenv
from urllib.parse import urlencode
from urllib.request import urlopen


def _eutils_get(program: str, own_params: dict) -> bytes:
    "E-utilities helper to get and return response"

    load_dotenv(find_dotenv())
    ncbi_email = os.getenv("NCBI_EMAIL")
    if not ncbi_email:
        raise RuntimeError("NCBI_EMAIL is not set - check your .env file")

    shared_params = {
        "db": "pubmed",
        "tool": "clinical-trial-landscape-agent",
        "email": ncbi_email,
    }

    params = {**own_params, **shared_params}

    query_string = urlencode(params)
    url_path = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{program}.fcgi?{query_string}"
    )
    time.sleep(0.34)

    with urlopen(url_path) as response:
        response_bytes = response.read()
    return response_bytes


def search_pubmed(query: str, max_results: int = 5) -> list[str]:
    "takes a search query and returns a list of matched PMIDs (as strings)"

    params = {
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }
    response_bytes = _eutils_get("esearch", params)
    data = json.loads(response_bytes)
    matched_pmids = data["esearchresult"]["idlist"]

    return matched_pmids


def fetch_abstract(pmid: str) -> dict[str, str]:

    params = {
        "id": pmid,
        "retmode": "xml",
    }
    response_bytes = _eutils_get("efetch", params)
    xml_text = response_bytes.decode("utf-8")
    return parse_abstract_xml(pmid, xml_text)


def parse_abstract_xml(pmid: str, xml_text: str) -> dict[str, str]:
    # parsing into element tree
    root = ET.fromstring(xml_text)

    # article title
    title_element = root.find(".//ArticleTitle")
    if title_element is not None:
        article_title = "".join(title_element.itertext())
    else:
        article_title = ""

    # abstract
    abstract_parts = []
    for child in root.findall(".//AbstractText"):
        if child.get("Label"):
            abstract_parts.append(f"{child.get('Label')}: {''.join(child.itertext())}")
        else:
            abstract_parts.append("".join(child.itertext()))
    abstract = "\n".join(abstract_parts)

    return {"pmid": pmid, "title": article_title, "abstract": abstract}


if __name__ == "__main__":
    matched_pmids = search_pubmed("Lighthouse II")
    print(matched_pmids)

    results = fetch_abstract("34536404")
    print(results)
