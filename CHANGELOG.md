# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Controlled product identity registry for mapping supplier-specific SKUs to canonical SKUs before comparison and margin analysis.
- Optional GTIN/EAN metadata with check-digit validation and collision detection.
- CLI `--identity-map` support so supplier SKU renames can still be treated as the same product instead of false added/removed rows.
- Runnable product identity-map example covering supplier aliases, canonical SKUs, and optional GTIN usage.
- End-to-end regression coverage proving identity-mapped supplier SKU changes still resolve the correct sales-catalog margin risk.

### Changed

- CSV report writes are now atomic so a failed replacement does not destroy an existing report.
- Product identity handling remains fail-closed: duplicate aliases, conflicting canonical identities, invalid GTINs, unknown JSON fields, and duplicate JSON keys are rejected instead of guessed or silently overwritten.

## [0.1.0] - 2026-08-25

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
