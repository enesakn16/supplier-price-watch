from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

from supplier_price_watch import PriceWatchError, SupplierQuote

MONEY_QUANTUM = Decimal("0.01")
ZERO = Decimal("0")
REQUIRED_COLUMNS = frozenset({"sku", "sale_price"})
CANONICAL_COLUMNS = REQUIRED_COLUMNS | {"currency"}


def _money(value: object, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PriceWatchError(f"{field} must be a valid decimal value") from exc
    if not result.is_finite():
        raise PriceWatchError(f"{field} must be finite")
    if result <= ZERO:
        raise PriceWatchError(f"{field} must be greater than zero")
    return result.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class SalePrice:
    sku: str
    sale_price: Decimal
    currency: str = "TRY"

    @classmethod
    def from_mapping(cls, row: dict[str, object]) -> "SalePrice":
        sku = str(row.get("sku", "")).strip()
        raw_currency = row.get("currency")
        currency = "TRY" if raw_currency is None else str(raw_currency).strip().upper() or "TRY"
        if not sku:
            raise PriceWatchError("sku is required")
        if len(currency) != 3 or not currency.isalpha():
            raise PriceWatchError("currency must be a 3-letter code")
        return cls(
            sku=sku,
            sale_price=_money(row.get("sale_price"), field="sale_price"),
            currency=currency,
        )


def load_sales_catalog_csv(path: str | Path) -> list[SalePrice]:
    """Load a strict UTF-8 CSV sales catalog.

    Required columns are ``sku`` and ``sale_price``. ``currency`` is optional and
    defaults to TRY. Duplicate ``sku + currency`` identities are rejected rather
    than silently overwritten.
    """

    csv_path = Path(path)
    try:
        handle = csv_path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise PriceWatchError(f"cannot read sales catalog CSV: {csv_path}") from exc

    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise PriceWatchError("sales catalog CSV header is required")

        headers = [name.strip() if name is not None else "" for name in reader.fieldnames]
        if any(not name for name in headers):
            raise PriceWatchError("sales catalog CSV contains an empty column name")
        if len(headers) != len(set(headers)):
            raise PriceWatchError("sales catalog CSV contains duplicate column names")

        unsupported = sorted(set(headers).difference(CANONICAL_COLUMNS))
        if unsupported:
            raise PriceWatchError(
                f"sales catalog CSV contains unsupported columns: {', '.join(unsupported)}"
            )
        missing = sorted(REQUIRED_COLUMNS.difference(headers))
        if missing:
            raise PriceWatchError(
                f"sales catalog CSV missing required columns: {', '.join(missing)}"
            )

        prices: list[SalePrice] = []
        seen: set[tuple[str, str]] = set()
        for line_number, raw_row in enumerate(reader, start=2):
            if None in raw_row:
                raise PriceWatchError(
                    f"sales catalog CSV row {line_number} has more values than headers"
                )
            if all(value is None or not str(value).strip() for value in raw_row.values()):
                continue
            try:
                price = SalePrice.from_mapping(dict(raw_row))
            except PriceWatchError as exc:
                raise PriceWatchError(
                    f"sales catalog CSV row {line_number}: {exc}"
                ) from exc

            identity = (price.sku, price.currency)
            if identity in seen:
                raise PriceWatchError(
                    f"sales catalog CSV row {line_number}: duplicate SKU/currency identity"
                )
            seen.add(identity)
            prices.append(price)

        return prices


def sale_price_mapping_for_quotes(
    sales_catalog: Iterable[SalePrice],
    current_quotes: Iterable[SupplierQuote],
) -> dict[str, Decimal]:
    """Build the legacy SKU->price mapping only when currency is unambiguous.

    ``compare_catalogs`` currently accepts sale prices keyed by SKU. This adapter
    keeps that API safe by refusing to produce a mapping when the same SKU appears
    in current supplier data under multiple currencies, or when a configured sale
    currency conflicts with the current quote currency. Missing sale prices are
    allowed and simply omit margin-risk calculation for that SKU.
    """

    catalog_index = {(item.sku, item.currency): item for item in sales_catalog}
    currencies_by_sku: dict[str, set[str]] = {}
    for quote in current_quotes:
        currencies_by_sku.setdefault(quote.sku, set()).add(quote.currency)

    result: dict[str, Decimal] = {}
    for sku, currencies in currencies_by_sku.items():
        if len(currencies) > 1:
            if any(key_sku == sku for key_sku, _ in catalog_index):
                raise PriceWatchError(
                    f"cannot apply SKU-only sale price to multi-currency supplier data: {sku}"
                )
            continue

        currency = next(iter(currencies))
        sale = catalog_index.get((sku, currency))
        if sale is not None:
            result[sku] = sale.sale_price
            continue

        conflicting = sorted(
            candidate_currency
            for candidate_sku, candidate_currency in catalog_index
            if candidate_sku == sku
        )
        if conflicting:
            raise PriceWatchError(
                f"sales catalog currency mismatch for {sku}: supplier uses {currency}, "
                f"sales catalog has {', '.join(conflicting)}"
            )

    return result
