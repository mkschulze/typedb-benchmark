import pytest
from tax_benchmark.costs import measured_cost
from tax_benchmark.providers import ModelDefinition


def priced_model(**updates):
    model = ModelDefinition(
        id="priced", name="Priced", model="test", input_price_per_million=2,
        output_price_per_million=10, cached_input_price_per_million=0.1, price_date="2026-11-21",
    )
    return model.model_copy(update={"cache_write_price_per_million": 5, **updates})


def complete_metrics(**updates):
    return {
        "input_tokens": 1000, "output_tokens": 100,
        "cached_tokens": 200, "cache_write_tokens": 300, **updates,
    }


def test_mixed_input_categories_charge_each_token_once_at_the_write_ceiling():
    # 500 normal * $2 + 200 reads * $0.10 + 300 writes * $5 + 100 output * $10.
    assert measured_cost(priced_model(), complete_metrics()) == pytest.approx(0.00352)


def test_known_cache_writes_keep_the_reservation_when_the_write_price_is_unknown():
    assert measured_cost(
        priced_model(cache_write_price_per_million=None), complete_metrics(),
    ) is None


@pytest.mark.parametrize("writes", [0, None])
def test_no_known_writes_preserve_the_legacy_complete_usage_estimate(writes):
    assert measured_cost(
        priced_model(cache_write_price_per_million=None), complete_metrics(cache_write_tokens=writes),
    ) == pytest.approx(0.00262)


def test_legacy_metrics_without_a_write_counter_still_have_an_estimate():
    assert measured_cost(
        priced_model(), {"input_tokens": 1000, "output_tokens": 100, "cached_tokens": 200},
    ) == pytest.approx(0.00262)


@pytest.mark.parametrize("counter", ["input_tokens", "output_tokens", "cached_tokens", "cache_write_tokens"])
@pytest.mark.parametrize("value", [-1, True, 1.5, "1", float("nan"), float("inf")])
def test_invalid_token_counts_cannot_release_a_reservation(counter, value):
    assert measured_cost(priced_model(), complete_metrics(**{counter: value})) is None


@pytest.mark.parametrize("counter", ["input_tokens", "output_tokens", "cached_tokens"])
def test_incomplete_input_output_or_read_counts_keep_the_cost_unknown(counter):
    assert measured_cost(priced_model(), complete_metrics(**{counter: None})) is None


def test_cache_reads_and_writes_cannot_exceed_total_input_tokens():
    assert measured_cost(
        priced_model(), complete_metrics(cached_tokens=800, cache_write_tokens=300),
    ) is None


def test_native_sol_long_context_keeps_its_reservation_instead_of_using_short_context_rates():
    model = priced_model(model="gpt-6.2-sol")

    assert measured_cost(model, complete_metrics(input_tokens=272001)) is None
    assert measured_cost(model, complete_metrics(input_tokens=272000)) == pytest.approx(0.54552)


@pytest.mark.parametrize("price_date", [None, "bad", 42])
def test_cache_write_estimates_require_valid_dated_prices(price_date):
    assert measured_cost(priced_model(price_date=price_date), complete_metrics()) is None


@pytest.mark.parametrize("field", [
    "input_price_per_million", "output_price_per_million",
    "cached_input_price_per_million", "cache_write_price_per_million",
])
@pytest.mark.parametrize("value", [None, -1, float("nan"), float("inf")])
def test_missing_or_invalid_prices_keep_mixed_token_costs_unknown(field, value):
    assert measured_cost(priced_model(**{field: value}), complete_metrics()) is None


def test_zero_reads_and_writes_do_not_require_unapplied_cache_prices():
    assert measured_cost(
        priced_model(cached_input_price_per_million=None, cache_write_price_per_million=None),
        complete_metrics(cached_tokens=0, cache_write_tokens=0),
    ) == pytest.approx(0.003)
