# Supplier Price Watch

Supplier Price Watch is a procurement-intelligence CLI for comparing recurring supplier price lists, detecting purchase-cost changes, identifying added/removed SKUs, and surfacing margin risk before supplier updates reach selling prices.

It is built for motorcycle-parts and e-commerce operations that need deterministic answers to five questions:

1. Which supplier SKUs became more expensive or cheaper?
2. Which SKUs were added to or removed from a supplier list?
3. Which rows can be compared safely without guessing product identity?
4. Which supplier file schemas changed and therefore require an explicit import-profile update?
5. Which matched SKUs now create `WARNING` or `CRITICAL` gross-margin risk against an explicit sales catalog?

> Status: **v0.1.0 release candidate.** CSV/XLSX ingestion, versioned supplier profiles, Decimal-based comparison, added/removed SKU reporting, sales-catalog margin risk, regression tests, packaging checks, and GitHub Actions CI are implemented. Real supplier-specific profiles must still be derived from verified source-file schemas rather than guessed.

## What works today

- Strict CSV ingestion with UTF-8 BOM support
- Strict XLSX ingestion through `openpyxl` in read-only/data-only mode
- Canonical `supplier`, `sku`, `unit_cost`, and optional `currency` fields
- `TRY` as the explicit default when currency is blank or omitted
- Explicit supplier-specific header mapping without fuzzy guessing
- Versioned `SupplierImportProfile` definitions with optional worksheet selection
- Strict JSON profile-registry loading with duplicate-key and unknown-field rejection
- Profile-bound supplier identity when a source file has no supplier column
- Fail-closed rejection when an embedded supplier conflicts with the selected profile
- Duplicate-column, missing-column, malformed-row, invalid-price, and duplicate-identity rejection
- `Decimal`-based purchase-price and gross-margin calculations
- Exact `supplier + SKU + currency` catalog matching
- Added/removed SKU detection between snapshots
- Sales-catalog ingestion with currency-safe matching
- `OK`, `WARNING`, and `CRITICAL` margin-risk classification
- Operational summary for price direction, catalog deltas, and margin-risk counts
- CLI comparison for `.csv` and `.xlsx` snapshots
- Optional UTF-8 CSV report export
- `--only-risk` filtering when a sales catalog is supplied
- Installable `supplier-price-watch` console command
- Unit/regression tests and GitHub Actions CI on Python 3.11 and 3.13

## Quick start

Python 3.11+ is required.

```bash
git clone https://github.com/enesakn16/supplier-price-watch.git
cd supplier-price-watch
python -m pip install -e .
python -m unittest discover -s tests -v
supplier-price-watch --help
```

Compare two canonical supplier snapshots:

```bash
supplier-price-watch previous.csv current.csv
```

Use XLSX input and write a CSV report:

```bash
supplier-price-watch previous.xlsx current.xlsx --output report.csv
```

Add an explicit sales catalog to calculate gross-margin risk:

```bash
supplier-price-watch previous.xlsx current.xlsx \
  --sales-catalog sales.csv \
  --output report.csv
```

Show only `WARNING` / `CRITICAL` matched rows while keeping the operational summary based on the full comparison set:

```bash
supplier-price-watch previous.xlsx current.xlsx \
  --sales-catalog sales.csv \
  --only-risk
```

The CLI returns exit code `2` for invalid input/profile/catalog conditions instead of continuing with a guessed result.

## Reproducible synthetic demo

The following demo uses only synthetic commercial data and exercises the full snapshot + catalog-delta + margin-risk path.

Create `previous.csv`:

```csv
supplier,sku,unit_cost,currency
Demo Supplier,TYRE-001,100.00,TRY
Demo Supplier,BRAKE-002,200.00,TRY
Demo Supplier,CHAIN-003,300.00,TRY
```

Create `current.csv`:

```csv
supplier,sku,unit_cost,currency
Demo Supplier,TYRE-001,120.00,TRY
Demo Supplier,BRAKE-002,180.00,TRY
Demo Supplier,FILTER-004,90.00,TRY
```

Create `sales.csv`:

```csv
sku,sale_price,currency
TYRE-001,130.00,TRY
BRAKE-002,300.00,TRY
FILTER-004,150.00,TRY
```

Run:

```bash
supplier-price-watch previous.csv current.csv \
  --sales-catalog sales.csv \
  --output report.csv
```

This scenario is intentionally chosen to produce all three operational signal types:

- `TYRE-001`: matched SKU with a purchase-cost increase and low gross margin, therefore a margin-risk signal
- `BRAKE-002`: matched SKU with a purchase-cost decrease and healthy margin
- `CHAIN-003`: `removed` from the current supplier snapshot
- `FILTER-004`: `added` in the current supplier snapshot

The command also writes `report.csv`, so the same deterministic output can be inspected or passed to a downstream spreadsheet/reporting step. No supplier identity, currency conversion, or product alias is inferred during this demo.

## Canonical supplier format

Canonical CSV input:

```csv
supplier,sku,unit_cost,currency
Supplier A,8690001,123.45,TRY
Supplier B,BTZ10S,1120.00,TRY
```

The same canonical field names can be used in XLSX workbooks.

A supplier-quote identity is:

```text
supplier + SKU + currency
```

Rows outside that exact identity are never silently paired.

## Sales catalog format

The optional sales catalog is intentionally explicit:

```csv
sku,sale_price,currency
8690001,169.90,TRY
BTZ10S,1499.00,TRY
```

Sales prices are matched currency-safely. A TRY supplier quote is never enriched with a USD selling price, and ambiguous multi-currency matches fail closed.

When a sale price is available, gross margin is calculated as:

```text
(sale price - current purchase cost) / sale price × 100
```

Default domain thresholds are:

- `CRITICAL`: gross margin <= 10%
- `WARNING`: gross margin <= 20%
- `OK`: gross margin > 20%

These are engine defaults, not a claim that the same commercial thresholds are correct for every business.

## Versioned supplier profiles

Real supplier sheets often use custom headers or omit a supplier column entirely. Supplier Price Watch handles that through explicit, versioned import contracts rather than header guessing.

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
supplier-price-watch old.xlsx new.xlsx \
  --profile-config supplier-profiles.json \
  --profile-id supplier-a
```

Omit `--profile-version` to select the latest configured version, or pin one explicitly:

```bash
supplier-price-watch old.xlsx new.xlsx \
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

## Matching policy

The matching layer is deliberately conservative:

```text
supplier + SKU + currency
```

Unmatched rows are reported as `added` or `removed`; they are not guessed from product descriptions. This prevents unrelated parts from being paired because their text happens to look similar.

A future identity layer may add controlled barcode/EAN and explicit SKU aliases. Fuzzy name matching, if introduced later, must remain review-only and must never silently create a purchasing match.

## Tests and CI

Run the deterministic suite locally with:

```bash
python -m unittest discover -s tests -v
```

The suite covers financial-domain rules, CSV/XLSX ingestion, supplier-profile behavior, strict JSON profile loading, supplierless imports, version resolution, catalog deltas, currency preservation, sales-catalog matching, margin-risk reporting, and CLI workflows.

GitHub Actions runs on Python 3.11 and 3.13 for pushes to `main` and pull requests. The release gate also performs dependency validation, installed-CLI smoke testing, and wheel/source-distribution builds.

## Security and commercial-data handling

Real supplier price lists can contain commercially sensitive information.

- Do not commit production supplier price lists.
- Do not commit supplier credentials, API keys, customer data, or private commercial terms.
- Fixtures and documentation examples must use synthetic data unless redistribution is explicitly permitted.
- Raw supplier files should remain immutable inputs; normalized records should be derived from them.
- Ambiguous product identities must fail closed and be surfaced for manual review.
- Supplier profiles must be derived from verified source-file schemas; do not invent production mappings from memory.
- Currency conversion is deliberately outside the comparison engine; different currencies are never treated as equivalent without an explicit external conversion step.

See [SECURITY.md](SECURITY.md) for the project security policy and [CHANGELOG.md](CHANGELOG.md) for release notes.

## Roadmap

The next high-value milestones are:

1. Add verified supplier-profile fixtures derived from real file headers, using synthetic row values
2. Add barcode/EAN and controlled SKU-alias identity mapping
3. Add purchasing-focused XLSX output with explicit review status
4. Add optional supplier/API adapters only where authentication and source contracts are well defined
5. Add a web UI or persistent database only if the CLI workflow proves that they are genuinely needed

## Release scope

The `0.1.0` release scope is deliberately narrow: deterministic supplier snapshot comparison, catalog-delta reporting, explicit sales-catalog margin risk, strict import profiles, local CLI operation, and regression-tested fail-closed behavior.

It does **not** claim live supplier integrations, automatic FX conversion, fuzzy product identity, hosted dashboards, or production supplier-profile mappings that have not been verified from source files.

## License

MIT. See [LICENSE](LICENSE).
