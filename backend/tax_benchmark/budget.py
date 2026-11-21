import json
from datetime import date
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from uuid import uuid4

from .storage import RunStore

_UNITS_PER_EUR = Decimal("1000000000")
_MAX_UNITS = 2**63 - 1


class BudgetError(RuntimeError):
    pass


def _decimal(value, name):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise BudgetError(f"{name} must be a finite nonnegative number") from error
    if not amount.is_finite() or amount < 0:
        raise BudgetError(f"{name} must be a finite nonnegative number")
    return amount


def _units(eur):
    if eur > Decimal(_MAX_UNITS) / _UNITS_PER_EUR:
        raise BudgetError("Amount exceeds the supported experiment budget")
    return int((eur * _UNITS_PER_EUR).to_integral_value(rounding=ROUND_CEILING))


class ExperimentBudget:
    """Reserve the maximum call cost before sending a billable request.

    A missing response keeps its reservation indefinitely. SQLite serializes the
    check and insert so different workers and restarts share the same allowance.
    """

    def __init__(
        self,
        store: RunStore,
        limit_eur=Decimal("30"),
        usd_per_eur=Decimal("1.0990"),
        safety_multiplier=Decimal("1.3"),
        today: date | None = None,
    ):
        limit_amount = _decimal(limit_eur, "EUR limit")
        if limit_amount > 30:
            raise BudgetError("The authorized experiment budget cannot exceed EUR 30")
        limit = _units(limit_amount)
        exchange_rate = _decimal(usd_per_eur, "USD per EUR")
        safety = _decimal(safety_multiplier, "Safety multiplier")
        if exchange_rate <= 0 or safety < 1:
            raise BudgetError("USD per EUR must be positive and the safety multiplier must be at least 1")
        self.store = store
        self._today_override = today
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS experiment_budget ("
                "id INTEGER PRIMARY KEY CHECK(id=1), limit_units INTEGER NOT NULL, "
                "usd_per_eur TEXT NOT NULL, safety_multiplier TEXT NOT NULL, "
                "blocked INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS experiment_budget_reservations ("
                "id TEXT PRIMARY KEY, purpose TEXT NOT NULL, reserved_units INTEGER NOT NULL, "
                "charged_units INTEGER NOT NULL, state TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO experiment_budget "
                "(id, limit_units, usd_per_eur, safety_multiplier) VALUES (1, ?, ?, ?)",
                (limit, str(exchange_rate), str(safety)),
            )
            saved = connection.execute(
                "SELECT limit_units, usd_per_eur, safety_multiplier FROM experiment_budget WHERE id=1"
            ).fetchone()
            if not 0 <= saved[0] <= _units(Decimal("30")):
                raise BudgetError("The persisted experiment budget must be between EUR 0 and EUR 30")
        self.limit_units = saved[0]
        self.usd_per_eur = Decimal(saved[1])
        self.safety_multiplier = Decimal(saved[2])

    @property
    def today(self) -> date:
        return self._today_override or date.today()

    def reserve_usd(self, amount_usd, purpose: str) -> str:
        amount = _decimal(amount_usd, "Reserved USD amount")
        reserved = _units(amount / self.usd_per_eur * self.safety_multiplier)
        reservation_id = str(uuid4())
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            limit, blocked = connection.execute(
                "SELECT limit_units, blocked FROM experiment_budget WHERE id=1"
            ).fetchone()
            charged = connection.execute(
                "SELECT COALESCE(SUM(charged_units), 0) FROM experiment_budget_reservations"
            ).fetchone()[0]
            if blocked or reserved > limit - charged:
                raise BudgetError("The shared experiment budget cannot cover another paid request")
            connection.execute(
                "INSERT INTO experiment_budget_reservations VALUES (?, ?, ?, ?, 'reserved')",
                (reservation_id, purpose, reserved, reserved),
            )
        return reservation_id

    def reserve_chat(self, model, messages: list[dict]) -> str:
        try:
            price_date = date.fromisoformat(model.price_date)
        except (TypeError, ValueError) as error:
            raise BudgetError("Paid models require dated input and output prices") from error
        if not 0 <= (self.today - price_date).days <= 14:
            raise BudgetError("Paid model prices must be verified within the last 14 days")
        if model.input_price_per_million is None or model.output_price_per_million is None:
            raise BudgetError("Paid models require dated input and output prices")
        input_price = _decimal(model.input_price_per_million, "Input token price")
        if model.cached_input_price_per_million is not None:
            input_price = max(
                input_price, _decimal(model.cached_input_price_per_million, "Cached input token price")
            )
        output_price = _decimal(model.output_price_per_million, "Output token price")
        # UTF-8 bytes bound text tokenization; extra framing covers provider-added tokens.
        input_tokens = (
            len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) + 4096 * (len(messages) + 1)
        )
        amount = (
            Decimal(input_tokens) * input_price
            + Decimal(model.max_output_tokens) * output_price
        ) * 2 / Decimal("1000000")
        return self.reserve_usd(amount, f"chat:{model.id}")

    def settle(self, reservation_id: str, actual_usd=None):
        actual = (
            None
            if actual_usd is None
            else _units(
                _decimal(actual_usd, "Actual USD amount") / self.usd_per_eur * self.safety_multiplier
            )
        )
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT reserved_units, charged_units, state FROM experiment_budget_reservations WHERE id=?",
                (reservation_id,),
            ).fetchone()
            if row is None:
                raise BudgetError("Unknown experiment budget reservation")
            reserved, charged, state = row
            if state == "settled":
                if actual is not None and actual != charged:
                    raise BudgetError("Recorded experiment spending cannot be rewritten")
                return
            if actual is None:
                connection.execute(
                    "UPDATE experiment_budget_reservations SET state='unreported' WHERE id=?",
                    (reservation_id,),
                )
                return
            connection.execute(
                "UPDATE experiment_budget_reservations SET charged_units=?, state='settled' WHERE id=?",
                (actual, reservation_id),
            )
            if actual > reserved:
                connection.execute("UPDATE experiment_budget SET blocked=1 WHERE id=1")

    def snapshot(self) -> dict:
        with self.store.connection() as connection:
            limit, blocked = connection.execute(
                "SELECT limit_units, blocked FROM experiment_budget WHERE id=1"
            ).fetchone()
            rows = connection.execute(
                "SELECT state, COALESCE(SUM(charged_units), 0), COUNT(*) "
                "FROM experiment_budget_reservations GROUP BY state"
            ).fetchall()
        amounts = {state: units for state, units, _ in rows}
        counts = {state: count for state, _, count in rows}
        spent = amounts.get("settled", 0)
        reserved = amounts.get("reserved", 0) + amounts.get("unreported", 0)
        committed = spent + reserved
        return {
            "limit_eur": float(Decimal(limit) / _UNITS_PER_EUR),
            "spent_eur": float(Decimal(spent) / _UNITS_PER_EUR),
            "reserved_eur": float(Decimal(reserved) / _UNITS_PER_EUR),
            "committed_eur": float(Decimal(committed) / _UNITS_PER_EUR),
            "remaining_eur": float(Decimal(max(0, limit - committed)) / _UNITS_PER_EUR),
            "usd_per_eur": float(self.usd_per_eur),
            "safety_multiplier": float(self.safety_multiplier),
            "blocked": bool(blocked or committed > limit),
            "pending_reservations": counts.get("reserved", 0),
            "unreported_reservations": counts.get("unreported", 0),
        }
