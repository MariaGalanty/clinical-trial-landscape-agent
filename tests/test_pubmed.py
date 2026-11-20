"""Plain Python checks for pubmed.py. Parsing is tested on a saved efetch response."""

from pathlib import Path
from pubmed import _eutils_get, parse_abstract_xml


def load_or_save_xml(pmid: str, path: Path) -> str:
    if not path.exists():
        response_bytes = _eutils_get("efetch", {"id": pmid, "retmode": "xml"})
        path.write_bytes(response_bytes)
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    pmid_nr = "34536404"
    FIXTURE_PATH = (
        Path(__file__).resolve().parent.parent / f"data/raw/pubmed_efetch_{pmid_nr}.xml"
    )
    xml_text = load_or_save_xml(pmid_nr, FIXTURE_PATH)
    parsed = parse_abstract_xml(pmid_nr, xml_text)
    print(parsed)
    assert parsed["pmid"] == pmid_nr, "pmid not passed through"
    assert parsed["title"] != "", "title is empty"
    assert parsed["abstract"] != "", "abstract is empty"
    assert "METHODS:" in parsed["abstract"], "section label missing"
    print("parse test passed")
