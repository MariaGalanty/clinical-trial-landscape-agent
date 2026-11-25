import hashlib
import json
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from tavily import TavilyClient

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "web"

# Pages that only repeat the registry, or rarely hold trial outcomes
EXCLUDED_DOMAINS = [
    "clinicaltrials.gov",
    "trial.medpath.com",
    "centerwatch.com",
    "smartpatients.com",
    "withpower.com",
    "trialscreen.org",
    "clinicaltrialsregister.eu",
]

load_dotenv(find_dotenv())
client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def _cache_path(kind: str, key: dict) -> Path:
    """One file per unique request. The name is a hash of every input that changes the answer."""
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]
    return CACHE_DIR / kind / f"{digest}.json"


def web_search(query: str, max_results: int = 10, refresh: bool = False) -> list[dict]:
    """Tavily search -> [{title, url, content}]. content is a short extract of the page."""
    key = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "exclude_domains": EXCLUDED_DOMAINS,
    }
    path = _cache_path("searches", key)
    if path.is_file() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))["results"]

    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="advanced",
        exclude_domains=EXCLUDED_DOMAINS,
    )
    results = [
        {"title": r["title"], "url": r["url"], "content": r["content"]}
        for r in response["results"]
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({**key, "results": results}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return results


def fetch_page(url: str, refresh: bool = False) -> str:
    """Full text of one page via Tavily Extract. "" if Tavily could not read it."""
    path = _cache_path("pages", {"url": url})
    if path.is_file() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))["text"]

    response = client.extract(urls=[url])
    text = response["results"][0]["raw_content"] if response["results"] else ""
    if text:  # don't cache failures: they may work next time
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"url": url, "text": text}, ensure_ascii=False),
            encoding="utf-8",
        )
    return text
