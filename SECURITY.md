# Security Policy

## Supported versions

`supplier-price-watch` is currently pre-1.0 software. Security fixes are applied to the latest code on `main` and, once published, the latest `0.x` release line.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| latest `0.x` release | Yes |
| older snapshots/releases | No |

## Reporting a vulnerability

Please do **not** open a public issue containing credentials, private supplier files, customer data, internal URLs, API keys, tokens, or other sensitive material.

Use GitHub's private vulnerability reporting feature for this repository when available. Include only the minimum information needed to reproduce the issue:

- affected version or commit;
- input format involved (`CSV`, `XLSX`, supplier profile, or sales catalog);
- a minimal **synthetic** reproducer;
- expected and actual behavior;
- security impact;
- whether the issue can cause incorrect supplier/SKU/currency matching, unsafe financial output, path/file handling problems, or disclosure of sensitive data.

Do not attach real supplier price lists. Replace supplier names, SKUs, barcodes, prices, paths, and any commercial information with synthetic examples unless that exact value is essential to reproduce the vulnerability.

## Security boundaries

This project treats imported supplier files and profile configuration as untrusted input.

### Fail-closed matching

Financial comparisons must not guess identity. Matching is intentionally strict around supplier, SKU, and currency. Ambiguous or conflicting identities should fail rather than silently producing a price or margin result.

Supplier import profiles may provide a trusted supplier identity and explicit column mapping, but they must not be used to bypass currency or duplicate-identity checks.

### Money handling

Money and percentage calculations use `Decimal`; converting the financial core to binary floating-point would weaken deterministic financial behavior and should be treated as a correctness regression.

### CSV/XLSX ingestion

Importers validate required columns, duplicate identities, malformed values, explicit supplier-profile mappings, and worksheet selection. Formula cells are not evaluated by the application; XLSX input is read in `data_only` mode.

Do not treat spreadsheet content as executable code. New features must not evaluate formulas, macros, shell commands, Python expressions, or arbitrary templates from imported files.

### Configuration and secrets

Supplier profile JSON is configuration, not a secret store. Do not commit or place the following in profile files, fixtures, examples, logs, screenshots, or generated reports:

- API keys or access tokens;
- database credentials;
- private supplier portal credentials;
- customer personal data;
- confidential supplier price lists;
- internal network addresses that should not be public.

Use synthetic fixtures for tests and documentation.

### Output safety

Generated reports may contain commercially sensitive pricing and margin information. The CLI writes only to paths explicitly supplied by the operator; deployments should apply appropriate filesystem permissions and retention rules outside the application.

## Dependency and CI policy

Pull requests and `main` changes should keep the automated test suite green. Release candidates should additionally verify that:

1. project dependencies install successfully;
2. `python -m pip check` reports no broken dependency graph;
3. the installed `supplier-price-watch --help` entry point starts successfully;
4. the unit/regression suite passes on the supported Python versions.

Dependency upgrades that affect CSV/XLSX parsing, packaging, or GitHub Actions should be reviewed against upstream release notes before merge.

## Out of scope

The project does not currently provide authentication, network services, secret management, malware scanning, or sandboxing for arbitrary uploaded files. Those controls belong to the system embedding the CLI/library and must not be implied by this repository.
