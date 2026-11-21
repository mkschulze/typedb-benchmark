import math
from datetime import date
from urllib.parse import urlsplit


def measured_cost(model, metrics):
    """Estimate USD from token usage, applying a verified write-price ceiling when needed."""
    if not isinstance(metrics, dict):
        return None
    try:
        date.fromisoformat(model.price_date)
    except (TypeError, ValueError):
        return None
    input_tokens, output_tokens, cached = (
        metrics.get(key) for key in ("input_tokens", "output_tokens", "cached_tokens")
    )
    # Older metrics lack this counter; preserve their existing estimate without changing the metrics.
    writes = metrics.get("cache_write_tokens")
    if writes is None:
        writes = 0
    if any(type(count) is not int or count < 0 for count in (input_tokens, output_tokens, cached, writes)):
        return None
    if cached + writes > input_tokens:
        return None
    if (
        model.model == "gpt-6.2-sol"
        and urlsplit(model.base_url).hostname == "api.openai.com"
        and input_tokens > 272_000
    ):
        # Sol's full-request rates increase above this threshold; short-context prices cannot settle it.
        return None
    input_price = model.input_price_per_million
    output_price = model.output_price_per_million
    cached_price = model.cached_input_price_per_million if cached else 0
    write_price = model.cache_write_price_per_million if writes else 0
    if any(
        type(price) not in (int, float) or not math.isfinite(price) or price < 0
        for price in (input_price, output_price, cached_price, write_price)
    ):
        return None
    try:
        cost = (
            (input_tokens - cached - writes) * input_price
            + cached * cached_price
            + writes * write_price
            + output_tokens * output_price
        ) / 1_000_000
    except OverflowError:
        return None
    return cost if math.isfinite(cost) else None
