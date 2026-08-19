from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from pathlib import Path
import sys
from typing import Iterable, Mapping

from sales_catalog import load_sales_catalog_csv, sale_price_mapping_for_quotes
from supplier_price_watch import (
    PriceComparison,
    PriceWatchError,
    RiskLevel,
    SupplierImportProfile,
    SupplierQuote,
    compare_catalogs,
    load_quotes_csv,
    load_quotes_csv_profile,
    load_quotes_xlsx,
    load_quotes_xlsx_profile,
)
from supplier_profile_config import load_profile_registry_json


QuoteIdentity = tuple[str, str, str]
MatchIdentity = tuple[str, str, Decimal, Decimal]


def _load_quotes(
    path: Path,
    *,
    profile: SupplierImportProfile | None = None,
) -> list[SupplierQuote]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        if profile is not None:
            return load_quotes_csv_profile(path, profile)
        return load_quotes_csv(path)
    if suffix == ".xlsx":
        if profile is not None:
            return load_quotes_xlsx_profile(path, profile)
        return load_quotes_xlsx(path)
    raise PriceWatchError("input files must be .csv or .xlsx")


def _resolve_profile(args: argparse.Namespace) -> SupplierImportProfile | None:
    requested = any(
        value is not None
        for value in (args.profile_config, args.profile_id, args.profile_version)
    )
    if not requested:
        return None
    if args.profile_config is None or args.profile_id is None:
        raise PriceWatchError(
            "--profile-config and --profile-id must be provided together"
        )

    registry = load_profile_registry_json(args.profile_config)
    return registry.get(args.profile_id, version=args.profile_version)


def _risk_rank(risk: RiskLevel) -> int:
    return {
        RiskLevel.CRITICAL: 0,
        RiskLevel.WARNING: 1,
        RiskLevel.OK: 2,
    }[risk]


def _sorted_results(results: Iterable[PriceComparison]) -> list[PriceComparison]:
    return sorted(
        results,
        key=lambda item: (
            _risk_rank(item.risk),
            -(item.percent_change or 0),
            item.supplier.casefold(),
            item.sku.casefold(),
        ),
    )


def _quote_identity(quote: SupplierQuote) -> QuoteIdentity:
    return (quote.supplier, quote.sku, quote.currency)


def _catalog_delta(
    previous: Iterable[SupplierQuote],
    current: Iterable[SupplierQuote],
) -> tuple[list[SupplierQuote], list[SupplierQuote]]:
    """Return newly added and removed exact supplier/SKU/currency identities."""

    previous_index = {_quote_identity(quote): quote for quote in previous}
    current_index = {_quote_identity(quote): quote for quote in current}

    added = [
        current_index[identity]
        for identity in sorted(
            current_index.keys() - previous_index.keys(),
            key=lambda value: tuple(part.casefold() for part in value),
        )
    ]
    removed = [
        previous_index[identity]
        for identity in sorted(
            previous_index.keys() - current_index.keys(),
            key=lambda value: tuple(part.casefold() for part in value),
        )
    ]
    return added, removed


def _matched_currency_lookup(
    previous: Iterable[SupplierQuote],
    current: Iterable[SupplierQuote],
) -> dict[MatchIdentity, str]:
    """Preserve currency for matched report rows without guessing ambiguous identities."""

    previous_index = {_quote_identity(quote): quote for quote in previous}
    currencies: dict[MatchIdentity, str] = {}

    for current_quote in current:
        previous_quote = previous_index.get(_quote_identity(current_quote))
        if previous_quote is None:
            continue

        key: MatchIdentity = (
            current_quote.supplier,
            current_quote.sku,
            previous_quote.unit_cost,
            current_quote.unit_cost,
        )
        existing = currencies.get(key)
        if existing is not None and existing != current_quote.currency:
            raise PriceWatchError(
                "ambiguous matched currency; supplier/SKU has indistinguishable "
                "cost rows in multiple currencies"
            )
        currencies[key] = current_quote.currency

    return currencies


def _format_decimal(value: object | None) -> str:
    return "" if value is None else str(value)


def _print_table(results: list[PriceComparison]) -> None:
    headers = ("supplier", "sku", "old", "new", "change", "%", "margin%", "risk")
    rows = [
        (
            item.supplier,
            item.sku,
            str(item.previous_cost),
            str(item.current_cost),
            str(item.absolute_change),
            _format_decimal(item.percent_change),
            _format_decimal(item.gross_margin_percent),
            item.risk.value,
        )
        for item in results
    ]
    widths = [len(value) for value in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render(row: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    print(render(headers))
    print(render(tuple("-" * width for width in widths)))
    for row in rows:
        print(render(row))


def _print_catalog_delta(
    added: list[SupplierQuote],
    removed: list[SupplierQuote],
) -> None:
    if not added and not removed:
        return

    print()
    print("Catalog changes:")
    for quote in added:
        print(
            f"+ ADDED    {quote.supplier} | {quote.sku} | "
            f"{quote.unit_cost} {quote.currency}"
        )
    for quote in removed:
        print(
            f"- REMOVED  {quote.supplier} | {quote.sku} | "
            f"{quote.unit_cost} {quote.currency}"
        )


def _write_csv(
    path: Path,
    results: list[PriceComparison],
    *,
    added: list[SupplierQuote],
    removed: list[SupplierQuote],
    matched_currencies: Mapping[MatchIdentity, str],
) -> None:
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "status",
                    "supplier",
                    "sku",
                    "currency",
                    "previous_cost",
                    "current_cost",
                    "absolute_change",
                    "percent_change",
                    "gross_margin_percent",
                    "risk",
                ]
            )
            for item in results:
                match_key: MatchIdentity = (
                    item.supplier,
                    item.sku,
                    item.previous_cost,
                    item.current_cost,
                )
                currency = matched_currencies.get(match_key)
                if currency is None:
                    raise PriceWatchError(
                        f"matched currency missing for {item.supplier}/{item.sku}"
                    )
                writer.writerow(
                    [
                        "matched",
                        item.supplier,
                        item.sku,
                        currency,
                        item.previous_cost,
                        item.current_cost,
                        item.absolute_change,
                        _format_decimal(item.percent_change),
                        _format_decimal(item.gross_margin_percent),
                        item.risk.value,
                    ]
                )
            for quote in added:
                writer.writerow(
                    [
                        "added",
                        quote.supplier,
                        quote.sku,
                        quote.currency,
                        "",
                        quote.unit_cost,
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            for quote in removed:
                writer.writerow(
                    [
                        "removed",
                        quote.supplier,
                        quote.sku,
                        quote.currency,
                        quote.unit_cost,
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
    except OSError as exc:
        raise PriceWatchError(f"cannot write report CSV: {path}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two supplier price-list snapshots. Exact supplier/SKU/currency "
            "matches are compared and catalog additions/removals are reported separately."
        )
    )
    parser.add_argument("previous", type=Path, help="Previous .csv or .xlsx price list")
    parser.add_argument("current", type=Path, help="Current .csv or .xlsx price list")
    parser.add_argument(
        "--profile-config",
        type=Path,
        help="Strict JSON file containing versioned supplier import profiles.",
    )
    parser.add_argument(
        "--profile-id",
        help="Profile ID to apply to both snapshots. Requires --profile-config.",
    )
    parser.add_argument(
        "--profile-version",
        type=int,
        help="Exact profile version. Omit to use the latest configured version.",
    )
    parser.add_argument(
        "--sales-catalog",
        type=Path,
        help=(
            "Optional strict CSV with sku,sale_price[,currency]. When supplied, "
            "matched rows include gross margin and OK/WARNING/CRITICAL risk."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional UTF-8 CSV report path. Table output is always printed.",
    )
    parser.add_argument(
        "--only-risk",
        action="store_true",
        help=(
            "Show only warning/critical matched rows. Requires --sales-catalog; "
            "catalog additions/removals remain visible."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.only_risk and args.sales_catalog is None:
            raise PriceWatchError("--only-risk requires --sales-catalog")

        profile = _resolve_profile(args)
        previous = _load_quotes(args.previous, profile=profile)
        current = _load_quotes(args.current, profile=profile)
        matched_currencies = _matched_currency_lookup(previous, current)

        sale_prices = None
        if args.sales_catalog is not None:
            sales_catalog = load_sales_catalog_csv(args.sales_catalog)
            sale_prices = sale_price_mapping_for_quotes(sales_catalog, current)

        results = _sorted_results(
            compare_catalogs(previous, current, sale_prices=sale_prices)
        )
        added, removed = _catalog_delta(previous, current)

        if args.only_risk:
            results = [item for item in results if item.risk is not RiskLevel.OK]

        if not results:
            print("No matching supplier/SKU/currency rows to report.")
        else:
            _print_table(results)
        _print_catalog_delta(added, removed)

        if args.output is not None:
            _write_csv(
                args.output,
                results,
                added=added,
                removed=removed,
                matched_currencies=matched_currencies,
            )
            print(f"Report written: {args.output}")
        return 0
    except PriceWatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
