"""One JSON line per LLM call: tokens, cost, latency. Works across providers."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "data" / "interim" / "llm_log.jsonl"

# Dated snapshot of LiteLLM's price list (scripts/update_llm_prices.py).
# A fixed file, not "latest": the same run always gives the same cost.
PRICES_FILE = PROJECT_ROOT / "config" / "model_prices_2026-11-19.json"

# Overrides for models missing from the snapshot or priced differently. USD per 1M tokens.
MANUAL_PRICES: dict[str, dict[str, float]] = {}


def load_prices(path: Path) -> dict[str, dict[str, float]]:
    """LiteLLM file (USD per token) -> {model: {input, cached_input, output}} in USD per 1M tokens."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    prices = {}
    for model, entry in raw.items():
        if "input_cost_per_token" not in entry or "output_cost_per_token" not in entry:
            continue  # e.g. embedding or image models
        p = {
            "input": round(entry["input_cost_per_token"] * 1_000_000, 6),
            "output": round(entry["output_cost_per_token"] * 1_000_000, 6),
        }
        if "cache_read_input_token_cost" in entry:
            p["cached_input"] = round(
                entry["cache_read_input_token_cost"] * 1_000_000, 6
            )
        if "cache_creation_input_token_cost" in entry:  # Anthropic cache writes
            p["cache_write"] = round(
                entry["cache_creation_input_token_cost"] * 1_000_000, 6
            )
        prices[model] = p
    return prices


PRICES = {**load_prices(PRICES_FILE), **MANUAL_PRICES}  # manual wins


def normalize_usage(provider: str, response: Any) -> dict[str, int | None]:
    """Turn each provider's usage object into the same fields."""
    if (
        provider == "langchain"
    ):  # AIMessage, or the dict from with_structured_output(include_raw=True)
        message = response["raw"] if isinstance(response, dict) else response
        u = message.usage_metadata or {}
        cached = (u.get("input_token_details") or {}).get("cache_read", 0) or 0
        return {
            "uncached_input": u.get("input_tokens", 0) - cached,
            "cached_input": cached,
            "cache_write": 0,
            "output": u.get("output_tokens", 0),
            "reasoning": (u.get("output_token_details") or {}).get("reasoning", 0) or 0,
        }
    u = response.usage
    if provider == "openai":  # Responses API (client.responses.create / .parse)
        cached = u.input_tokens_details.cached_tokens or 0
        return {
            "uncached_input": u.input_tokens - cached,  # OpenAI input INCLUDES cached
            "cached_input": cached,
            "cache_write": 0,
            "output": u.output_tokens,  # already includes reasoning tokens
            "reasoning": u.output_tokens_details.reasoning_tokens or 0,
        }
    if provider == "anthropic":  # Messages API
        return {
            "uncached_input": u.input_tokens,  # Anthropic input EXCLUDES cached
            "cached_input": u.cache_read_input_tokens or 0,
            "cache_write": u.cache_creation_input_tokens or 0,
            "output": u.output_tokens,  # already includes thinking tokens
            "reasoning": None,  # not reported separately
        }
    raise ValueError(f"Unknown provider: {provider}")


def cost_usd(model: str, usage: dict) -> float | None:
    """Tokens -> dollars. None if we don't know the model's price."""
    price = PRICES.get(model)
    if price is None:
        return None  # unknown price -> None, never a silent 0
    # Missing cache price -> charge full input price (overestimate, never underestimate)
    return (
        usage["uncached_input"] * price["input"]
        + usage["cached_input"] * price.get("cached_input", price["input"])
        + usage["cache_write"] * price.get("cache_write", price["input"] * 1.25)
        + usage["output"] * price["output"]
    ) / 1_000_000


def _append(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def logged_call(
    call: Callable[[], Any],
    *,
    provider: str,
    model: str,
    handler: str,
    nct_id: str,
    run_id: str,
) -> Any:
    """Run one LLM call, time it, log tokens and cost, return the response."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "nct_id": nct_id,
        "handler": handler,
        "provider": provider,
        "model": model,
    }
    start = time.perf_counter()
    try:
        response = call()
    except Exception as e:
        record.update(
            latency_s=round(time.perf_counter() - start, 3), ok=False, error=repr(e)
        )
        _append(record)  # failed calls are logged too
        raise
    record["latency_s"] = round(time.perf_counter() - start, 3)
    usage = normalize_usage(provider, response)
    record.update(usage)
    record.update(cost_usd=cost_usd(model, usage), ok=True, error=None)
    _append(record)
    return response
