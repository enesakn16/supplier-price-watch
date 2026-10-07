# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased] - 0.2.0

### Added

- Controlled product identity registry for mapping supplier-specific SKUs to canonical SKUs before comparison and margin analysis.
- Optional GTIN/EAN metadata with check-digit validation and collision detection.
- CLI `--identity-map` support so supplier SKU renames can still be treated as the same product instead of false added/removed rows.
- Deterministic unresolved-SKU review through `ProductIdentityRegistry.unresolved_quotes()`.
- Optional `--require-identity-alias` CLI enforcement and `require_alias=True` library behavior for controlled purchasing runs that must reject every unmapped supplier SKU.
- Purchasing-focused XLSX export with summary metrics, risk-prioritized review rows, filtering, and frozen headers.
- Installable `supplier-price-watch-xlsx` console command.
- Runnable product identity-map example covering supplier aliases, canonical SKUs, optional GTIN usage, unresolved identity handling, and strict alias enforcement.
- End-to-end regression coverage proving identity-mapped supplier SKU changes still resolve the correct sales-catalog margin risk.
- Regression coverage for deterministic unresolved-SKU ordering, strict alias enforcement, XLSX workbook structure, risk ordering, and canonical report-schema validation.

### Changed

- CSV report writes are now atomic so a failed replacement does not destroy an existing report.
- Purchasing workbook writes are atomic so failed exports do not leave partial output files.
- CSV reports neutralize formula-leading supplier/SKU text, and the standalone XLSX converter neutralizes every imported report cell, to prevent spreadsheet formula injection.
- Product identity handling remains fail-closed: duplicate aliases, conflicting canonical identities, invalid GTINs, unknown JSON fields, duplicate JSON keys, post-alias collisions, and optionally unresolved aliases are rejected instead of guessed or silently overwritten.
- CI validates built wheel and source distributions with strict Twine metadata checks before release work proceeds.

### Known limitations

- No live supplier API integration or automatic downloads; input files are user-provided snapshots.
- No fuzzy SKU matching, automatic barcode matching, or automatic alias creation.
- No built-in notification/alert delivery.
- Real supplier-specific profiles and identity aliases should only be added from verified source data.

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
