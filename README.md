# Supplier Price Watch

Supplier Price Watch is a lightweight procurement intelligence tool for comparing supplier price lists, detecting meaningful cost changes, and surfacing margin risk before those changes reach marketplace pricing.

It is designed for businesses that receive recurring supplier CSV/XLSX price lists and need a repeatable way to answer three questions:

1. Which SKUs became more expensive or cheaper?
2. Which changes materially reduce gross margin?
3. Which supplier currently offers the best verified purchase price for the same product?

> Status: **In development.** The repository is being initialized deliberately; do not use it for production purchasing decisions until the parser, matching rules, tests, and CI are present and green.

## Planned workflow

```text
Supplier CSV/XLSX files
        ↓
Normalize supplier rows
        ↓
Match by barcode / supplier SKU / controlled alias
        ↓
Compare previous and current cost
        ↓
Calculate margin impact
        ↓
Emit actionable risk report
```

The matching layer will prefer stable identifiers such as **EAN/barcode** and explicit supplier SKU mappings. Fuzzy product-name matching may be used only as an opt-in review aid; it must not silently merge products.

## Core product rules

- Monetary calculations use `Decimal`, never binary floating-point arithmetic.
- Raw supplier files remain immutable inputs; normalized data is derived from them.
- Missing/ambiguous SKU matches fail closed and are reported for manual review.
- A price change is not considered trustworthy unless the source row and supplier are traceable.
- Margin calculations must distinguish net purchase cost, VAT/tax treatment, marketplace commission, shipping, and other configurable costs.
- No supplier credential, API key, private price list, customer data, or production secret belongs in the repository.

## Planned MVP

The first working version will provide:

- CSV/XLSX supplier import adapters
- barcode/SKU based product matching
- previous-vs-current purchase price comparison
- absolute and percentage price delta
- configurable sale price and cost inputs
- gross-margin and margin-risk calculation
- best-supplier comparison per SKU
- CSV report export
- deterministic unit tests for money and matching rules
- GitHub Actions CI

## Example output

```text
SKU        Supplier       Old Cost   New Cost   Change    Margin Risk
6457       Supplier A      820.00     895.00     +9.15%    HIGH
BTZ10S     Supplier B     1120.00    1110.00     -0.89%    NONE
20400      Supplier C      245.00     279.00    +13.88%    MEDIUM
```

Exact thresholds will be configuration-driven rather than hard-coded business assumptions.

## Target project structure

```text
supplier-price-watch/
├── src/
│   └── supplier_price_watch/
│       ├── importers/
│       ├── matching.py
│       ├── pricing.py
│       ├── risk.py
│       └── models.py
├── tests/
├── examples/
├── .github/workflows/ci.yml
├── .gitignore
├── pyproject.toml
└── README.md
```

## Technology direction

- Python 3.11+
- standard-library `decimal.Decimal` for financial arithmetic
- `openpyxl` for XLSX ingestion where required
- `pytest` for deterministic tests
- GitHub Actions for CI

Dependencies will stay intentionally small. A web UI, database, or hosted service will only be added if the product actually needs one.

## Security and data handling

Real supplier price lists may contain commercially sensitive information. Example fixtures committed to this repository must therefore be synthetic. Configuration examples must contain placeholders only. Secrets will be supplied through environment variables or an external secret store if integrations are added later.

## Definition of done for the first release

A first release is not ready until a user can import two synthetic supplier snapshots, obtain a deterministic SKU-level change report, identify margin-risk rows, run the full test suite locally, and see the same tests pass in CI.

## License

A license will be selected before the first public release. Until then, no reuse rights should be inferred beyond GitHub's normal repository viewing/forking functionality.
