# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.1.0] - Unreleased

### Added

- Strict CSV and XLSX supplier quote ingestion with fail-closed schema validation.
- Explicit, versioned supplier import profiles with JSON configuration support.
- Exact `supplier + SKU + currency` matching; no fuzzy or silent cross-currency matching.
- `Decimal`-based price change and gross-margin calculations.
- Sales catalog ingestion and `OK / WARNING / CRITICAL` margin-risk classification.
- CLI support for CSV/XLSX comparisons, supplier profiles, sales catalogs, CSV report export, and risk-only filtering.
- Added/removed SKU detection between supplier snapshots.
- Operational summary covering matched SKUs, price increases/decreases, unchanged items, added/removed items, and margin-risk counts.
- Python 3.11/3.13 CI and regression coverage for parsing, profile resolution, currency handling, CLI output, margin risk, and catalog deltas.

### Security and correctness

- Rejects malformed prices, duplicate identities, invalid currencies, unsupported schemas, and ambiguous multi-currency matches instead of guessing.
- Supplier profiles may provide trusted supplier identity when source files omit a supplier column; conflicting source values are rejected.
- XLSX files are opened read-only/data-only and closed reliably.

### Known limitations

- No live supplier API integration or automatic downloads; input files are user-provided snapshots.
- No fuzzy SKU matching or barcode alias registry yet.
- No built-in notification/alert delivery yet.
- Real supplier-specific profiles should only be added from verified source file schemas.
