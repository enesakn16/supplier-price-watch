from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from typing import Iterable, Mapping

MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


class PriceWatchError(ValueError):
    """Raised when supplier-price input is incomplete or financially unsafe."""


class RiskLevel(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PriceWatchError(f"{field} must be a valid decimal value") from exc
    if not result.is_finite():
        raise PriceWatchError(f"{field} must be finite")
    return result


def _money(value: object, *, field: str) -> Decimal:
    result = _decimal(value, field=field)
    if result < ZERO:
        raise PriceWatchError(f"{field} cannot be negative")
    return result.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class SupplierQuote:
    supplier: str
    sku: str
    unit_cost: Decimal
    currency: str = "TRY"

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "SupplierQuote":
        supplier = str(row.get("supplier", "")).strip()
        sku = str(row.get("sku", "")).strip()
        currency = str(row.get("currency", "TRY")).strip().upper() or "TRY"
        if not supplier:
            raise PriceWatchError("supplier is required")
        if not sku:
            raise PriceWatchError("sku is required")
        if len(currency) != 3 or not currency.isalpha():
            raise PriceWatchError("currency must be a 3-letter code")
        return cls(
            supplier=supplier,
            sku=sku,
            unit_cost=_money(row.get("unit_cost"), field="unit_cost"),
            currency=currency,
        )


@dataclass(frozen=True, slots=True)
class PriceComparison:
    supplier: str
    sku: str
    previous_cost: Decimal
    current_cost: Decimal
    absolute_change: Decimal
    percent_change: Decimal | None
    gross_margin_percent: Decimal | None
    risk: RiskLevel


def compare_quote(
    previous: SupplierQuote,
    current: SupplierQuote,
    *,
    sale_price: object | None = None,
    warning_margin_percent: object = "20",
    critical_margin_percent: object = "10",
) -> PriceComparison:
    """Compare one supplier quote with its prior value using Decimal math.

    The comparison fails closed when supplier, SKU or currency differ. Margin risk
    is only calculated when a sale price is explicitly provided.
    """

    if previous.supplier != current.supplier:
        raise PriceWatchError("supplier mismatch")
    if previous.sku != current.sku:
        raise PriceWatchError("sku mismatch")
    if previous.currency != current.currency:
        raise PriceWatchError("currency mismatch; convert explicitly before comparison")

    absolute_change = (current.unit_cost - previous.unit_cost).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )
    percent_change = None
    if previous.unit_cost != ZERO:
        percent_change = (
            absolute_change / previous.unit_cost * HUNDRED
        ).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)

    gross_margin_percent = None
    risk = RiskLevel.OK

    if sale_price is not None:
        sale = _money(sale_price, field="sale_price")
        if sale == ZERO:
            raise PriceWatchError("sale_price must be greater than zero")

        warning = _decimal(warning_margin_percent, field="warning_margin_percent")
        critical = _decimal(critical_margin_percent, field="critical_margin_percent")
        if warning < ZERO or critical < ZERO:
            raise PriceWatchError("margin thresholds cannot be negative")
        if critical > warning:
            raise PriceWatchError("critical margin threshold cannot exceed warning threshold")

        gross_margin_percent = (
            (sale - current.unit_cost) / sale * HUNDRED
        ).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)

        if gross_margin_percent <= critical:
            risk = RiskLevel.CRITICAL
        elif gross_margin_percent <= warning:
            risk = RiskLevel.WARNING

    return PriceComparison(
        supplier=current.supplier,
        sku=current.sku,
        previous_cost=previous.unit_cost,
        current_cost=current.unit_cost,
        absolute_change=absolute_change,
        percent_change=percent_change,
        gross_margin_percent=gross_margin_percent,
        risk=risk,
    )


def compare_catalogs(
    previous_quotes: Iterable[SupplierQuote],
    current_quotes: Iterable[SupplierQuote],
    *,
    sale_prices: Mapping[str, object] | None = None,
) -> list[PriceComparison]:
    """Compare matching supplier/SKU/currency rows and ignore unmatched rows.

    Unmatched items are intentionally not guessed. Callers can separately report
    additions/removals instead of accidentally pairing unrelated supplier data.
    """

    old_index = {
        (quote.supplier, quote.sku, quote.currency): quote for quote in previous_quotes
    }
    results: list[PriceComparison] = []

    for current in current_quotes:
        previous = old_index.get((current.supplier, current.sku, current.currency))
        if previous is None:
            continue
        sale_price = sale_prices.get(current.sku) if sale_prices else None
        results.append(compare_quote(previous, current, sale_price=sale_price))

    return results
