from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
from typing import Iterable

from supplier_price_watch import (
    PriceComparison,
    PriceWatchError,
    RiskLevel,
    SupplierQuote,
    compare_catalogs,
    load_quotes_csv,
    load_quotes_xlsx,
)


def _load_quotes(path: Path) -> list[SupplierQuote]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_quotes_csv(path)
    if suffix == ".xlsx":
        return load_quotes_xlsx(path)
    raise PriceWatchError("input files must be .csv or .xlsx")


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


def _write_csv(path: Path, results: list[PriceComparison]) -> None:
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "supplier",
                    "sku",
                    "previous_cost",
                    "current_cost",
                    "absolute_change",
                    "percent_change",
                    "gross_margin_percent",
                    "risk",
                ]
            )
            for item in results:
                writer.writerow(
                    [
                        item.supplier,
                        item.sku,
                        item.previous_cost,
                        item.current_cost,
                        item.absolute_change,
                        _format_decimal(item.percent_change),
                        _format_decimal(item.gross_margin_percent),
                        item.risk.value,
                    ]
                )
    except OSError as exc:
        raise PriceWatchError(f"cannot write report CSV: {path}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two supplier price-list snapshots. Only exact "
            "supplier/SKU/currency matches are compared."
        )
    )
    parser.add_argument("previous", type=Path, help="Previous .csv or .xlsx price list")
    parser.add_argument("current", type=Path, help="Current .csv or .xlsx price list")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional UTF-8 CSV report path. Table output is always printed.",
    )
    parser.add_argument(
        "--only-risk",
        action="store_true",
        help="Show only warning/critical rows. Requires margin data in future catalog workflows.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        previous = _load_quotes(args.previous)
        current = _load_quotes(args.current)
        results = _sorted_results(compare_catalogs(previous, current))
        if args.only_risk:
            results = [item for item in results if item.risk is not RiskLevel.OK]

        if not results:
            print("No matching supplier/SKU/currency rows to report.")
        else:
            _print_table(results)

        if args.output is not None:
            _write_csv(args.output, results)
            print(f"Report written: {args.output}")
        return 0
    except PriceWatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
