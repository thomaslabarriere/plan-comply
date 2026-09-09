"""Token pricing for the inference-cost line.

USD per 1M tokens (input / output). ILLUSTRATIVE public list prices, used only
to turn token usage into a rough dollar-per-document figure for the ROI framing
(manual expert minutes vs. automated cost). They drift, so treat the number as
an order of magnitude, not a bill. An unknown model yields no estimate.
"""

from __future__ import annotations

_PRICES: dict[str, tuple[float, float]] = {
    # model: (input_per_million, output_per_million)
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4.1-nano": (0.1, 0.4),
}


def model_from_applier(applier_name: str) -> str | None:
    """The model behind an applier name like 'llm:gpt-4o' (None for others)."""
    if applier_name.startswith("llm:"):
        return applier_name[len("llm:") :]
    return None


def estimate_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Rough USD for the given usage, or None if the model price is unknown."""
    if model is None:
        return None
    price = _PRICES.get(model) or _PRICES.get(model.removeprefix("openai/"))
    if price is None:
        return None
    input_per_m, output_per_m = price
    return prompt_tokens / 1_000_000 * input_per_m + completion_tokens / 1_000_000 * output_per_m
