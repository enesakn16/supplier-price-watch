# Supplier Price Watch

Supplier Price Watch is a procurement-intelligence CLI for comparing recurring supplier price lists, detecting purchase-cost changes, identifying added/removed products, and surfacing gross-margin risk before supplier updates reach selling prices.

It is built for motorcycle-parts and e-commerce operations that need deterministic answers to six questions:

1. Which supplier products became more expensive or cheaper?
2. Which products were added to or removed from a supplier list?
3. Did a supplier change its SKU for an existing product?
4. Which rows can be compared safely without guessing product identity?
5. Which supplier file schemas changed and require an explicit import-profile update?
6. Which matched products now create `WARNING` or `CRITICAL` gross-margin risk against the sales catalog?

> Status: **v0.2.0 codebase; GitHub release/tag pending.** CSV/XLSX ingestion, versioned supplier profiles, controlled supplier-SKU → canonical-SKU identity mapping with optional validated GTIN metadata, Decimal-based comparison, catalog-delta reporting, sales-catalog margin risk, regression tests, packaging checks, and GitHub Actions CI are implemented. Real supplier-specific profiles and identity aliases must be derived from verified source data rather than guessed.

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
- Controlled supplier SKU → canonical SKU aliases through `--identity-map`
- Optional validated GTIN-8/12/13/14 metadata in identity aliases
- Duplicate alias, conflicting barcode, invalid GTIN, and post-alias duplicate-identity rejection
- Duplicate-column, missing-column, malformed-row, invalid-price, and duplicate-identity rejection
- `Decimal`-based purchase-price and gross-margin calculations
- Exact `supplier + canonical SKU + currency` comparison after optional identity normalization
- Added/removed product detection between snapshots
- Sales-catalog ingestion with currency-safe canonical-SKU matching
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

Add a sales catalog and write the result:

```bash
supplier-price-watch previous.xlsx current.xlsx \
  --sales-catalog sales.csv \
  --output report.csv
```

When supplier SKUs changed between snapshots, normalize them before comparison:

```bash
supplier-price-watch previous.csv current.csv \
  --identity-map product-identities.json \
  --sales-catalog sales.csv \
  --output report.csv
```

Show only `WARNING` / `CRITICAL` matched rows while keeping the operational summary based on the full comparison set:

```bash
supplier-price-watch previous.xlsx current.xlsx \
  --sales-catalog sales.csv \
  --only-risk
```

The CLI returns exit code `2` for invalid input, profile, identity-map, or catalog conditions instead of continuing with a guessed result.

## Reproducible synthetic demo

This demo exercises SKU replacement, canonical matching, price-change detection, sales-catalog enrichment, and margin risk without exposing real commercial data.

Create `previous.csv`:

```csv
supplier,sku,unit_cost,currency
Demo Supplier,OLD-TYRE-42,100.00,TRY
Demo Supplier,BRAKE-002,200.00,TRY
```

Create `current.csv`:

```csv
supplier,sku,unit_cost,currency
Demo Supplier,NEW-TYRE-42,120.00,TRY
Demo Supplier,BRAKE-002,180.00,TRY
```

Create `product-identities.json`:

```json
[
  {
    "supplier": "Demo Supplier",
    "source_sku": "OLD-TYRE-42",
    "canonical_sku": "TYRE-42"
  },
  {
    "supplier": "Demo Supplier",
    "source_sku": "NEW-TYRE-42",
    "canonical_sku": "TYRE-42"
  }
]
```

Create `sales.csv` using the canonical SKU:

```csv
sku,sale_price,currency
TYRE-42,130.00,TRY
BRAKE-002,300.00,TRY
```

Run:

```bash
supplier-price-watch previous.csv current.csv \
  --identity-map product-identities.json \
  --sales-catalog sales.csv \
  --output report.csv
```

The two supplier-specific tyre SKUs are normalized to `TYRE-42` before comparison. The result is therefore one matched product with a real cost increase and margin-risk calculation, not a false `removed` + `added` pair. `BRAKE-002` remains an exact match and requires no alias.

No fuzzy name matching, currency conversion, barcode guess, or automatic alias creation occurs.

## Canonical supplier format

Canonical CSV input:

```csv
supplier,sku,unit_cost,currency
Supplier A,8690001,123.45,TRY
Supplier B,BTZ10S,1120.00,TRY
```

The same canonical field names can be used in XLSX workbooks.

Without an identity map, a supplier quote identity is:

```text
supplier + supplier SKU + currency
```

With an identity map, the SKU is first normalized and comparison uses:

```text
supplier + canonical SKU + currency
```

Rows outside that deterministic identity are never silently paired.

## Product identity map

Use `--identity-map` only for product identities that have been verified from a trustworthy source such as supplier master data, an internal SKU cross-reference, or a validated barcode mapping.

The file is a strict JSON array:

```json
[
  {
    "supplier": "Supplier A",
    "source_sku": "A-OLD-100",
    "canonical_sku": "BRAKE-PAD-100",
    "barcode": "4006381333931"
  }
]
```

Required fields:

- `supplier`: supplier identity used in the price-list row
- `source_sku`: SKU exactly as supplied by that supplier
- `canonical_sku`: stable SKU used for comparison and sales-catalog lookup

Optional `barcode` values must be valid GTIN-8, GTIN-12, GTIN-13, or GTIN-14 values including a valid check digit. A barcode is supporting identity metadata; the CLI does not infer aliases from barcodes automatically.

The registry is deliberately fail-closed. It rejects unknown JSON fields, duplicate JSON keys, duplicate supplier/SKU aliases, one barcode mapped to conflicting canonical SKUs, invalid GTINs, and aliases that collapse multiple rows into the same `supplier + canonical SKU + currency` identity.

Unmapped SKUs remain unchanged. This lets a file contain a mix of stable supplier SKUs and a small reviewed alias set without forcing unnecessary mappings.

## Sales catalog format

The optional sales catalog is intentionally explicit:

```csv
sku,sale_price,currency
BRAKE-PAD-100,169.90,TRY
BTZ10S,1499.00,TRY
```

When `--identity-map` is used, the sales catalog should use canonical SKUs. Sales prices are matched currency-safely. A TRY supplier quote is never enriched with a USD selling price, and ambiguous multi-currency matches fail closed.

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
  --profile-id supplier-a \
  --identity-map product-identities.json
```

Omit `--profile-version` to select the latest configured version, or pin one explicitly with `--profile-version 1`.

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

The matching layer is deliberately conservative. Supplier SKU normalization happens only when an explicit trusted alias exists. Unmatched rows are reported as `added` or `removed`; they are not guessed from product descriptions.

Fuzzy name matching is intentionally unsupported for purchasing identity. If a future review-assistance layer proposes possible matches, it must remain non-authoritative until a human verifies and records the alias.

## Tests and CI

Run the deterministic suite locally with:

```bash
python -m unittest discover -s tests -v
```

The suite covers financial-domain rules, CSV/XLSX ingestion, supplier-profile behavior, strict JSON loading, supplierless imports, version resolution, controlled product identity aliases, GTIN validation, post-alias collision rejection, catalog deltas, currency preservation, sales-catalog matching, margin-risk reporting, and CLI workflows including SKU replacement across snapshots.

GitHub Actions runs on Python 3.11 and 3.13 for pushes to `main` and pull requests. The release gate also performs dependency validation, installed-CLI smoke testing, and wheel/source-distribution builds.

## Security and commercial-data handling

Real supplier price lists and identity mappings can contain commercially sensitive information.

- Do not commit production supplier price lists.
- Do not commit confidential SKU cross-reference files unless they are explicitly safe for publication.
- Do not commit supplier credentials, API keys, customer data, or private commercial terms.
- Fixtures and documentation examples must use synthetic data unless redistribution is explicitly permitted.
- Raw supplier files should remain immutable inputs; normalized records should be derived from them.
- Ambiguous product identities must fail closed and be surfaced for manual review.
- Supplier profiles and identity aliases must come from verified source data; do not invent production mappings from memory.
- Currency conversion is deliberately outside the comparison engine; different currencies are never treated as equivalent without an explicit external conversion step.

See [SECURITY.md](SECURITY.md) for the project security policy and [CHANGELOG.md](CHANGELOG.md) for release notes.

## Roadmap

The next high-value milestones are:

1. Add verified supplier-profile fixtures derived from real file headers, using synthetic row values
2. Add purchasing-focused XLSX output with explicit review status
3. Add an identity-review workflow for unresolved supplier SKU changes without auto-matching them
4. Add optional supplier/API adapters only where authentication and source contracts are well defined
5. Add a web UI or persistent database only if the CLI workflow proves that they are genuinely needed

## Release scope

The `0.2.0` codebase is deliberately scoped: deterministic supplier snapshot comparison, catalog-delta reporting, controlled product identity aliases with validated GTIN metadata, explicit sales-catalog margin risk, strict import profiles, local CLI operation, and regression-tested fail-closed behavior.

It does **not** claim live supplier integrations, automatic FX conversion, fuzzy product identity, hosted dashboards, or production supplier-profile/identity mappings that have not been verified from source data.

## License

MIT. See [LICENSE](LICENSE).