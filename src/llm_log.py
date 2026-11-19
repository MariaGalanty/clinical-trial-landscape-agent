"""One JSON line per LLM call: tokens, cost, latency. Works across providers."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "interim" / "llm_log.jsonl"

# USD per 1M tokens. Copy from each provider's pricing page; prices change.
# Checked: 2026-11-19
PRICES: dict[str, dict[str, float]] = {
    # OpenAI, https://openai.com/api/pricing - fill in before running:
    # "gpt-5.4-nano": {"input": ..., "cached_input": ..., "output": ...},
    "claude-sonnet-5-5": {"input": 2.00, "cached_input": 0.10, "output": 10.00},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},  # prompts up to 100K tokens
}


def normalize_usage(provider: str, response: Any) -> dict[str, int | None]:
    """Turn each provider's usage object into the same fields."""
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
