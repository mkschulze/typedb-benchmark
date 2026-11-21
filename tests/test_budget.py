from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
from tax_benchmark.budget import BudgetError, ExperimentBudget
from tax_benchmark.providers import ModelDefinition
from tax_benchmark.storage import RunStore

TODAY = date(2026, 11, 21)


def budget_for(tmp_path, **kwargs):
    return ExperimentBudget(
        RunStore(tmp_path / "runs.sqlite"),
        usd_per_eur=Decimal("1"),
        safety_multiplier=Decimal("1"),
        today=TODAY,
        **kwargs,
    )


def priced_model(**kwargs):
    return ModelDefinition(
        id="priced",
        name="Priced",
        model="test",
        input_price_per_million=1,
        output_price_per_million=2,
        price_date="2026-11-20",
        **kwargs,
    )


def test_all_providers_and_restarts_share_the_initial_cap(tmp_path):
    budget = budget_for(tmp_path, limit_eur=Decimal("20"))
    first = budget.reserve_usd(Decimal("10"), "provider-a")
    budget.settle(first, Decimal("6"))
    restarted = budget_for(tmp_path, limit_eur=Decimal("30"))
    restarted.reserve_usd(Decimal("14"), "provider-b")

    with pytest.raises(BudgetError):
        budget.reserve_usd(Decimal("0.000001"), "provider-c")

    snapshot = restarted.snapshot()
    assert snapshot["limit_eur"] == 20
    assert snapshot["spent_eur"] == 6
    assert snapshot["reserved_eur"] == 14
    assert snapshot["remaining_eur"] == 0


def test_initial_configuration_cannot_exceed_the_authorized_30_eur(tmp_path):
    with pytest.raises(BudgetError):
        budget_for(tmp_path, limit_eur=Decimal("999"))


def test_a_persisted_cap_above_the_authorized_limit_is_rejected(tmp_path):
    budget = budget_for(tmp_path)
    with budget.store.connection() as connection:
        connection.execute("UPDATE experiment_budget SET limit_units=31000000000 WHERE id=1")
    with pytest.raises(BudgetError):
        budget_for(tmp_path)


def test_fx_and_safety_apply_to_reservations_and_settled_spending(tmp_path):
    budget = ExperimentBudget(
        RunStore(tmp_path / "runs.sqlite"),
        usd_per_eur=Decimal("2"),
        safety_multiplier=Decimal("1.3"),
    )
    reservation = budget.reserve_usd(Decimal("10"), "embedding")
    assert budget.snapshot()["reserved_eur"] == 6.5

    budget.settle(reservation, Decimal("8"))
    snapshot = budget.snapshot()
    assert snapshot["spent_eur"] == 5.2
    assert snapshot["reserved_eur"] == 0
    assert snapshot["remaining_eur"] == 24.8


def test_default_exchange_rate_and_margin_protect_the_euro_cap(tmp_path):
    budget = ExperimentBudget(RunStore(tmp_path / "runs.sqlite"))
    reservation = budget.reserve_usd(Decimal("10.99"), "paid")
    assert budget.snapshot()["reserved_eur"] == 13
    budget.settle(reservation, Decimal("5.495"))
    assert budget.snapshot()["spent_eur"] == 6.5


def test_unreported_spending_keeps_its_bound_after_a_restart(tmp_path):
    budget = budget_for(tmp_path)
    reservation = budget.reserve_usd(Decimal("30"), "timeout")
    budget.settle(reservation)
    restarted = budget_for(tmp_path)

    with pytest.raises(BudgetError):
        restarted.reserve_usd(Decimal("0.01"), "next")
    assert restarted.snapshot()["reserved_eur"] == 30
    assert restarted.snapshot()["unreported_reservations"] == 1


def test_a_crashed_request_keeps_its_reservation(tmp_path):
    budget_for(tmp_path).reserve_usd(Decimal("30"), "crashed")
    restarted = budget_for(tmp_path)
    with pytest.raises(BudgetError):
        restarted.reserve_usd(Decimal("1"), "next")
    assert restarted.snapshot()["pending_reservations"] == 1


def test_concurrent_reservations_cannot_exceed_the_shared_cap(tmp_path):
    budgets = [budget_for(tmp_path) for _ in range(12)]

    def reserve(budget):
        try:
            return budget.reserve_usd(Decimal("10"), "parallel")
        except BudgetError:
            return None

    with ThreadPoolExecutor(max_workers=12) as executor:
        reservations = list(executor.map(reserve, budgets))

    assert sum(item is not None for item in reservations) == 3
    assert budgets[0].snapshot()["committed_eur"] == 30


def test_actual_spend_exceeding_a_reservation_permanently_blocks_new_calls(tmp_path):
    budget = budget_for(tmp_path)
    reservation = budget.reserve_usd(Decimal("1"), "underestimated")
    budget.settle(reservation, Decimal("2"))

    assert budget.snapshot()["spent_eur"] == 2
    assert budget.snapshot()["blocked"]
    with pytest.raises(BudgetError):
        budget_for(tmp_path).reserve_usd(Decimal("0.01"), "next")


def test_settlement_is_idempotent_and_cannot_rewrite_recorded_spending(tmp_path):
    budget = budget_for(tmp_path)
    reservation = budget.reserve_usd(Decimal("5"), "chat")
    budget.settle(reservation, Decimal("3"))
    budget.settle(reservation, Decimal("3"))
    budget.settle(reservation)
    with pytest.raises(BudgetError):
        budget.settle(reservation, Decimal("0"))
    assert budget.snapshot()["spent_eur"] == 3


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity", "-Infinity", "garbage"])
def test_invalid_money_cannot_create_or_release_reservations(tmp_path, amount):
    budget = budget_for(tmp_path)
    with pytest.raises(BudgetError):
        budget.reserve_usd(amount, "bad")
    reservation = budget.reserve_usd(Decimal("5"), "valid")
    with pytest.raises(BudgetError):
        budget.settle(reservation, amount)
    assert budget.snapshot()["reserved_eur"] == 5


def test_positive_subunit_reservations_are_rounded_up(tmp_path):
    budget = budget_for(tmp_path, limit_eur=Decimal("0.000001"))
    budget.reserve_usd(Decimal("0.00000000000000001"), "tiny")
    assert budget.snapshot()["reserved_eur"] > 0


def test_chat_reserves_for_input_framing_output_and_premium_rates(tmp_path):
    budget = budget_for(tmp_path)
    budget.reserve_chat(priced_model(max_output_tokens=1000), [{"role": "user", "content": "é"}])
    # JSON contains 35 UTF-8 bytes, framing adds 8192, then both rates double.
    assert budget.snapshot()["reserved_eur"] == 0.020454


def test_chat_reserves_using_the_highest_input_price_even_for_cached_tokens(tmp_path):
    budget = budget_for(tmp_path)
    model = priced_model(max_output_tokens=1000, cached_input_price_per_million=5)
    budget.reserve_chat(model, [{"role": "user", "content": "é"}])
    assert budget.snapshot()["reserved_eur"] == 0.08627


def test_chat_reserves_using_the_cache_write_ceiling_before_the_premium_multiplier(tmp_path):
    budget = budget_for(tmp_path)
    model = priced_model(max_output_tokens=1000, cached_input_price_per_million=5).model_copy(
        update={"cache_write_price_per_million": 7}
    )
    budget.reserve_chat(model, [{"role": "user", "content": "é"}])
    # 8227 input tokens at $7 plus 1000 output tokens at $2, all doubled.
    assert budget.snapshot()["reserved_eur"] == 0.119178


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf")])
def test_chat_refuses_invalid_cache_write_price_ceilings(tmp_path, price):
    model = priced_model().model_copy(update={"cache_write_price_per_million": price})

    with pytest.raises(BudgetError):
        budget_for(tmp_path).reserve_chat(model, [{"role": "user", "content": "hello"}])


def test_verified_cache_write_prices_expire_with_the_other_token_prices(tmp_path):
    budget = budget_for(tmp_path)
    model = priced_model().model_copy(
        update={"cache_write_price_per_million": 5, "price_date": "2026-11-07"}
    )
    messages = [{"role": "user", "content": "hello"}]
    budget.reserve_chat(model, messages)

    with pytest.raises(BudgetError, match="14 days"):
        budget.reserve_chat(model.model_copy(update={"price_date": "2026-11-06"}), messages)


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf")])
def test_chat_refuses_invalid_cache_prices(tmp_path, price):
    model = priced_model().model_copy(update={"cached_input_price_per_million": price})
    with pytest.raises(BudgetError):
        budget_for(tmp_path).reserve_chat(model, [{"role": "user", "content": "hello"}])


@pytest.mark.parametrize("price_date", [None, "bad", "2026-11-22", "2026-11-06"])
def test_chat_refuses_missing_stale_or_future_prices(tmp_path, price_date):
    model = priced_model().model_copy(update={"price_date": price_date})
    with pytest.raises(BudgetError):
        budget_for(tmp_path).reserve_chat(model, [{"role": "user", "content": "hello"}])


def test_a_running_server_rechecks_price_freshness_when_the_date_changes(tmp_path, monkeypatch):
    class RollingDate(date):
        current = TODAY

        @classmethod
        def today(cls):
            return cls.current

    monkeypatch.setattr("tax_benchmark.budget.date", RollingDate)
    budget = ExperimentBudget(RunStore(tmp_path / "runs.sqlite"))
    model = priced_model()
    messages = [{"role": "user", "content": "hello"}]
    budget.reserve_chat(model, messages)

    RollingDate.current = date(2026, 12, 5)
    with pytest.raises(BudgetError):
        budget.reserve_chat(model, messages)


@pytest.mark.parametrize("field", ["input_price_per_million", "output_price_per_million"])
@pytest.mark.parametrize("price", [None, -1, float("nan"), float("inf")])
def test_chat_refuses_unknown_or_invalid_prices(tmp_path, field, price):
    model = priced_model().model_copy(update={field: price})
    with pytest.raises(BudgetError):
        budget_for(tmp_path).reserve_chat(model, [{"role": "user", "content": "hello"}])


def test_unknown_reservation_cannot_be_settled(tmp_path):
    with pytest.raises(BudgetError):
        budget_for(tmp_path).settle("not-a-reservation", Decimal("0"))
