"""Download a dated snapshot of LiteLLM's model price list. Run by hand when prices need refreshing."""

import json
from datetime import date
from pathlib import Path
from urllib.request import urlopen

URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
MODELS_WE_USE = ["gpt-5.4", "claude-sonnet-5-5", "claude-haiku-5-5"]

out_dir = Path(__file__).resolve().parent.parent / "config"
out_path = out_dir / f"model_prices_{date.today().isoformat()}.json"

with urlopen(URL, timeout=30) as response:
    prices = json.load(response)

out_dir.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(prices, indent=1), encoding="utf-8")
print(f"Saved {len(prices)} models to {out_path}")

for model in MODELS_WE_USE:
    info = prices.get(model)
    if info is None:
        print(f"  MISSING: {model} - add it to MANUAL_PRICES by hand")
    else:
        print(
            f"  {model}: input ${info.get('input_cost_per_token', 0) * 1e6:.2f}/1M, "
            f"output ${info.get('output_cost_per_token', 0) * 1e6:.2f}/1M"
        )
