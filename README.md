# Supplier Price Watch

Supplier Price Watch is a lightweight procurement intelligence tool for comparing recurring supplier price lists, detecting purchase-cost changes, and surfacing gross-margin risk before those changes reach selling prices.

It is built for motorcycle-parts and e-commerce operations that need a deterministic answer to three questions:

1. Which supplier SKUs became more expensive or cheaper?
2. Which cost changes materially reduce gross margin?
3. Which rows cannot be compared safely and therefore need manual review?

> Status: **In development, working CSV MVP.** Strict CSV ingestion, explicit supplier column mapping, Decimal-based price comparison, margin-risk classification, regression tests, and GitHub Actions CI are implemented. XLSX ingestion, richer product identity mapping, and report export are still pending.

## What works today

- Strict CSV supplier-list ingestion with UTF-8 BOM support
- Required `supplier`, `sku`, and `unit_cost` fields
- Optional `currency` field with `TRY` default
- Explicit supplier-specific header mapping without guessing
- Duplicate-column, missing-column, malformed-row, and duplicate-identity rejection
- `Decimal`-based purchase-price calculations and financial rounding
- Absolute and percentage purchase-cost change calculation
- Gross-margin calculation from an explicitly supplied sale price
- `OK`, `WARNING`, and `CRITICAL` margin-risk classification
- Exact `supplier + SKU + currency` catalog matching
- Fail-closed behavior for supplier, SKU, or currency mismatches
- Unit/regression tests
- GitHub Actions CI on Python 3.11 and 3.13

## Quick start

The current CSV core uses only the Python standard library.

```bash
git clone https://github.com/enesakn16/supplier-price-watch.git
cd supplier-price-watch
python -m unittest discover -s tests -v
```

Minimal comparison example:

```python
from supplier_price_watch import SupplierQuote, compare_quote

previous = SupplierQuote.from_mapping(
    {
        "supplier": "Supplier A",
        "sku": "BTZ10S",
        "unit_cost": "1120.00",
        "currency": "TRY",
    }
)

current = SupplierQuote.from_mapping(
    {
        "supplier": "Supplier A",
        "sku": "BTZ10S",
        "unit_cost": "1215.00",
        "currency": "TRY",
    }
)

result = compare_quote(previous, current, sale_price="1499.00")

print(result.absolute_change)
print(result.percent_change)
print(result.gross_margin_percent)
print(result.risk.value)
```

## Supplier CSV format

Canonical input:

```csv
supplier,sku,unit_cost,currency
Arzu Bisiklet,8690001,123.45,TRY
MSR,BTZ10S,1120.00,TRY
```

Supplier-specific headers must be mapped explicitly. The loader intentionally does **not** guess column meanings:

```python
from supplier_price_watch import load_quotes_csv

quotes = load_quotes_csv(
    "supplier-list.csv",
    column_map={
        "Tedarikci": "supplier",
        "Urun Kodu": "sku",
        "Alis Fiyati": "unit_cost",
        "Para Birimi": "currency",
    },
)
```

If a mapped source column does not exist, two source columns collide into one canonical field, a row contains extra values, or the same `supplier + SKU + currency` identity appears twice, loading fails instead of silently inventing a result.

## Price and margin rules

All monetary arithmetic uses `decimal.Decimal`; binary floating-point arithmetic is not used for purchasing or margin decisions.

A quote comparison is allowed only when supplier, SKU, and currency match exactly. Currency conversion is deliberately outside the comparison engine: TRY and USD quotes are never compared as if they were equivalent.

When a sale price is supplied, gross margin is calculated as:

```text
(sale price - current purchase cost) / sale price × 100
```

The default risk boundaries are:

- `CRITICAL`: gross margin <= 10%
- `WARNING`: gross margin <= 20%
- `OK`: gross margin > 20%

These thresholds can be overridden per comparison. They are defaults for the engine, not claims about the correct commercial policy for every business.

## Matching policy

The current catalog comparison intentionally matches only the exact tuple:

```text
supplier + SKU + currency
```

Unmatched rows are ignored rather than guessed. This prevents unrelated products from being paired because their descriptions look similar.

The next matching layer will add controlled barcode/EAN and explicit alias support. Fuzzy name matching, if added later, will be review-only and must never silently create a purchasing match.

## Test and CI status

Run the same deterministic test suite locally with:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions executes the suite on Python 3.11 and 3.13 for pushes to `main` and pull requests. The latest implemented CSV column-profile change is green in CI.

## Security and data handling

Real supplier price lists can contain commercially sensitive pricing information.

- Do not commit production supplier lists.
- Do not commit supplier credentials, API keys, customer data, or private commercial terms.
- Test fixtures and examples must use synthetic data.
- Raw supplier files should remain immutable inputs; normalized records should be derived from them.
- Ambiguous product identities must fail closed and be surfaced for manual review.

## Roadmap

The next high-value milestones are:

1. XLSX ingestion using the same explicit column-profile rules as CSV
2. Barcode/EAN and controlled SKU-alias identity mapping
3. Added/removed SKU reporting instead of silently dropping unmatched catalog rows
4. Best verified supplier-price comparison per product
5. CSV report export suitable for purchasing review
6. Packaging with `pyproject.toml` and a small command-line interface
7. Synthetic end-to-end fixtures and a first tagged release

A web UI, database, or hosted service will only be added if the product actually needs one.

## Definition of done for the first release

The first public release is not ready until a user can import two synthetic supplier snapshots, obtain a deterministic SKU-level change report, identify margin-risk rows, review additions/removals, run the full test suite locally, and see the same suite pass in CI.

## License

A license will be selected before the first public release. Until then, no reuse rights should be inferred beyond GitHub's normal repository viewing and forking functionality.
