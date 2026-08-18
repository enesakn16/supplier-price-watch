# Supplier Price Watch

Supplier Price Watch is a procurement-intelligence tool for comparing recurring supplier price lists, detecting purchase-cost changes, and surfacing financially unsafe catalog changes before they reach selling prices.

It is built for motorcycle-parts and e-commerce operations that need deterministic answers to four questions:

1. Which supplier SKUs became more expensive or cheaper?
2. Which rows can be compared safely without guessing product identity?
3. Which supplier file schemas changed and therefore require an explicit import profile update?
4. Which results need purchasing review before price or stock decisions are made?

> Status: **In development, working CSV/XLSX + CLI MVP.** Strict CSV/XLSX ingestion, versioned supplier profiles, Decimal-based price comparison, regression tests, and GitHub Actions CI are implemented. Barcode/EAN identity mapping, added/removed SKU reporting, verified real-supplier profile fixtures, and the first public release are still pending.

## What works today

- Strict CSV ingestion with UTF-8 BOM support
- Strict XLSX ingestion through `openpyxl` in read-only/data-only mode
- Canonical `supplier`, `sku`, `unit_cost`, and optional `currency` fields
- `TRY` as the explicit default when currency is blank or omitted
- Explicit supplier-specific header mapping without fuzzy guessing
- Versioned `SupplierImportProfile` definitions with optional worksheet selection
- Strict JSON profile registry loading with duplicate-key and unknown-field rejection
- Profile-bound supplier identity, so a trusted profile can supply the supplier name even when the source file has no supplier column
- Fail-closed rejection when an embedded supplier conflicts with the selected profile
- Duplicate-column, missing-column, malformed-row, invalid-price, and duplicate-identity rejection
- `Decimal`-based purchase-price calculations and financial rounding
- Absolute and percentage purchase-cost change calculation
- Gross-margin calculation when an explicit sale price is supplied to the domain API
- `OK`, `WARNING`, and `CRITICAL` margin-risk classification
- Exact `supplier + SKU + currency` catalog matching
- Command-line comparison for `.csv` and `.xlsx` snapshots
- Optional UTF-8 CSV comparison report export
- Unit/regression tests
- GitHub Actions CI on Python 3.11 and 3.13

## Quick start

Python 3.11+ is required.

```bash
git clone https://github.com/enesakn16/supplier-price-watch.git
cd supplier-price-watch
python -m pip install -e .
python -m unittest discover -s tests -v
```

Compare two canonical snapshots from the terminal:

```bash
python supplier_price_watch_cli.py previous.csv current.csv
```

Write the comparison to a report as well:

```bash
python supplier_price_watch_cli.py previous.xlsx current.xlsx --output report.csv
```

The CLI returns exit code `2` for invalid input/profile conditions instead of continuing with a guessed result.

## Canonical supplier format

Canonical CSV input:

```csv
supplier,sku,unit_cost,currency
Supplier A,8690001,123.45,TRY
Supplier B,BTZ10S,1120.00,TRY
```

The same canonical field names can be used in XLSX workbooks.

A quote identity is currently:

```text
supplier + SKU + currency
```

Rows outside that exact identity are never silently paired.

## Versioned supplier profiles

Real supplier sheets often use their own headers or omit a supplier column entirely. Supplier Price Watch handles that through explicit, versioned import contracts rather than header guessing.

Example profile configuration:

```json
[
  {
    "profile_id": "supplier-a",
    "supplier": "Supplier A",
    "version": 1,
    "column_map": {
      "Urun Kodu": "sku",
      "Alis Fiyati": "unit_cost",
      "Para Birimi": "currency"
    },
    "sheet_name": "Fiyat Listesi"
  }
]
```

Use it from the CLI:

```bash
python supplier_price_watch_cli.py old.xlsx new.xlsx \
  --profile-config supplier-profiles.json \
  --profile-id supplier-a
```

Omit `--profile-version` to select the latest configured version, or pin one explicitly:

```bash
python supplier_price_watch_cli.py old.xlsx new.xlsx \
  --profile-config supplier-profiles.json \
  --profile-id supplier-a \
  --profile-version 1
```

Profiles are intentionally strict. Unknown JSON fields, duplicate JSON keys, invalid versions, duplicate profile/version pairs, unsupported canonical targets, missing mapped source columns, and supplier-identity mismatches fail closed.

## Python API example

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

## Price and margin rules

All monetary arithmetic uses `decimal.Decimal`; binary floating-point arithmetic is not used for purchasing or margin decisions.

Currency conversion is deliberately outside the comparison engine: TRY and USD quotes are never compared as if they were equivalent.

When a sale price is supplied to `compare_quote`, gross margin is calculated as:

```text
(sale price - current purchase cost) / sale price × 100
```

Default domain thresholds are:

- `CRITICAL`: gross margin <= 10%
- `WARNING`: gross margin <= 20%
- `OK`: gross margin > 20%

These thresholds can be overridden by callers. They are engine defaults, not a claim about the correct commercial policy for every business.

> Current CLI catalog comparison does not yet enrich rows with sale prices. Margin-risk output therefore becomes useful only after sale-price/catalog enrichment is added. The CLI does not pretend otherwise.

## Matching policy

The current matching layer is intentionally conservative:

```text
supplier + SKU + currency
```

Unmatched rows are not guessed from product descriptions. This prevents two unrelated parts from being paired because their text happens to look similar.

The next identity layer will add controlled barcode/EAN and explicit SKU aliases. Fuzzy name matching, if introduced later, will be review-only and must never silently create a purchasing match.

## Tests and CI

Run the full deterministic suite locally with:

```bash
python -m unittest discover -s tests -v
```

The tests cover the financial domain, CSV/XLSX ingestion, supplier profile rules, strict JSON profile loading, supplierless profile imports, version resolution, and CLI profile workflows.

GitHub Actions runs the suite on Python 3.11 and 3.13 for pushes to `main` and pull requests.

## Security and commercial-data handling

Real supplier price lists can contain commercially sensitive information.

- Do not commit production supplier price lists.
- Do not commit supplier credentials, API keys, customer data, or private commercial terms.
- Fixtures and documentation examples must use synthetic data unless redistribution is explicitly permitted.
- Raw supplier files should remain immutable inputs; normalized records should be derived from them.
- Ambiguous product identities must fail closed and be surfaced for manual review.
- Supplier profiles must be derived from verified source-file schemas; do not invent production mappings from memory.

## Roadmap

The next high-value milestones are:

1. Add verified supplier-profile fixtures derived from real file headers, using synthetic row values
2. Add barcode/EAN and controlled SKU-alias identity mapping
3. Report added/removed SKUs instead of silently dropping unmatched catalog rows
4. Enrich comparisons with an explicit sale-price catalog for real margin-risk CLI reports
5. Produce purchasing-focused CSV/XLSX reports with review status
6. Add release notes, changelog, license, and the first tagged release

A web UI, database, or hosted service will only be added if the product actually needs one.

## Definition of done for the first public release

The first public release is not ready until a user can import two synthetic supplier snapshots, select a verified versioned import profile, obtain a deterministic SKU-level change report, review additions/removals, identify margin-risk rows from an explicit sale-price source, run the full test suite locally, and see the same suite pass in CI.

## License

A license will be selected before the first public release. Until then, no reuse rights should be inferred beyond GitHub's normal repository viewing and forking functionality.
