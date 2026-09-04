from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from supplier_price_watch import PriceWatchError, SupplierQuote

_GTIN_LENGTHS = frozenset({8, 12, 13, 14})
_REQUIRED_ALIAS_FIELDS = frozenset({"supplier", "source_sku", "canonical_sku"})
_OPTIONAL_ALIAS_FIELDS = frozenset({"barcode"})
_ALIAS_FIELDS = _REQUIRED_ALIAS_FIELDS | _OPTIONAL_ALIAS_FIELDS


def _clean_text(value: object, *, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise PriceWatchError(f"{field} is required")
    return text


def _validate_gtin(value: object) -> str:
    barcode = _clean_text(value, field="barcode")
    if len(barcode) not in _GTIN_LENGTHS or any(ch < "0" or ch > "9" for ch in barcode):
        raise PriceWatchError("barcode must be a valid GTIN-8/12/13/14 digit string")

    body = barcode[:-1]
    expected = int(barcode[-1])
    weighted_sum = 0
    for index, digit in enumerate(reversed(body), start=1):
        weighted_sum += int(digit) * (3 if index % 2 == 1 else 1)
    actual = (10 - weighted_sum % 10) % 10
    if actual != expected:
        raise PriceWatchError("barcode has an invalid GTIN check digit")
    return barcode


@dataclass(frozen=True, slots=True)
class ProductIdentityAlias:
    """Trusted mapping from a supplier SKU (and optional GTIN) to one canonical SKU."""

    supplier: str
    source_sku: str
    canonical_sku: str
    barcode: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "supplier", _clean_text(self.supplier, field="supplier"))
        object.__setattr__(self, "source_sku", _clean_text(self.source_sku, field="source_sku"))
        object.__setattr__(
            self,
            "canonical_sku",
            _clean_text(self.canonical_sku, field="canonical_sku"),
        )
        if self.barcode is not None:
            object.__setattr__(self, "barcode", _validate_gtin(self.barcode))

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "ProductIdentityAlias":
        unknown = sorted(set(row).difference(_ALIAS_FIELDS))
        if unknown:
            raise PriceWatchError(f"identity alias contains unknown fields: {', '.join(unknown)}")
        missing = sorted(field for field in _REQUIRED_ALIAS_FIELDS if field not in row)
        if missing:
            raise PriceWatchError(f"identity alias missing required fields: {', '.join(missing)}")
        return cls(
            supplier=row["supplier"],
            source_sku=row["source_sku"],
            canonical_sku=row["canonical_sku"],
            barcode=row.get("barcode"),
        )


class ProductIdentityRegistry:
    """Deterministic alias registry; fuzzy matching is intentionally unsupported."""

    def __init__(self, aliases: Iterable[ProductIdentityAlias] = ()) -> None:
        self._supplier_skus: dict[tuple[str, str], ProductIdentityAlias] = {}
        self._barcodes: dict[str, str] = {}
        for alias in aliases:
            self.register(alias)

    def register(self, alias: ProductIdentityAlias) -> None:
        sku_key = (alias.supplier, alias.source_sku)
        if sku_key in self._supplier_skus:
            raise PriceWatchError(
                f"duplicate identity alias for supplier/SKU: {alias.supplier}/{alias.source_sku}"
            )

        if alias.barcode is not None:
            existing = self._barcodes.get(alias.barcode)
            if existing is not None and existing != alias.canonical_sku:
                raise PriceWatchError(
                    f"barcode maps to multiple canonical SKUs: {alias.barcode}"
                )

        self._supplier_skus[sku_key] = alias
        if alias.barcode is not None:
            self._barcodes[alias.barcode] = alias.canonical_sku

    def resolve_supplier_sku(self, supplier: str, source_sku: str) -> str | None:
        key = (
            _clean_text(supplier, field="supplier"),
            _clean_text(source_sku, field="source_sku"),
        )
        alias = self._supplier_skus.get(key)
        return None if alias is None else alias.canonical_sku

    def resolve_barcode(self, barcode: str) -> str | None:
        return self._barcodes.get(_validate_gtin(barcode))

    def canonicalize_quote(self, quote: SupplierQuote) -> SupplierQuote:
        canonical_sku = self.resolve_supplier_sku(quote.supplier, quote.sku)
        if canonical_sku is None or canonical_sku == quote.sku:
            return quote
        return SupplierQuote(
            supplier=quote.supplier,
            sku=canonical_sku,
            unit_cost=quote.unit_cost,
            currency=quote.currency,
        )

    def canonicalize_quotes(self, quotes: Iterable[SupplierQuote]) -> list[SupplierQuote]:
        result: list[SupplierQuote] = []
        seen: set[tuple[str, str, str]] = set()
        for quote in quotes:
            canonical = self.canonicalize_quote(quote)
            identity = (canonical.supplier, canonical.sku, canonical.currency)
            if identity in seen:
                raise PriceWatchError(
                    "identity aliases create duplicate supplier/SKU/currency identity: "
                    f"{canonical.supplier}/{canonical.sku}/{canonical.currency}"
                )
            seen.add(identity)
            result.append(canonical)
        return result

    def list_aliases(self) -> tuple[ProductIdentityAlias, ...]:
        return tuple(
            sorted(
                self._supplier_skus.values(),
                key=lambda item: (
                    item.supplier.casefold(),
                    item.source_sku.casefold(),
                    item.canonical_sku.casefold(),
                ),
            )
        )


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PriceWatchError(f"identity map contains duplicate JSON key: {key}")
        result[key] = value
    return result


def load_identity_registry_json(path: str | Path) -> ProductIdentityRegistry:
    """Load a strict JSON array of trusted product-identity aliases."""

    config_path = Path(path)
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PriceWatchError(f"cannot read identity map: {config_path}") from exc

    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
    except PriceWatchError:
        raise
    except json.JSONDecodeError as exc:
        raise PriceWatchError(f"invalid identity-map JSON: {exc.msg}") from exc

    if not isinstance(raw, list):
        raise PriceWatchError("identity map must be a JSON array")

    aliases: list[ProductIdentityAlias] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            raise PriceWatchError(f"identity alias {index} must be a JSON object")
        try:
            aliases.append(ProductIdentityAlias.from_mapping(item))
        except PriceWatchError as exc:
            raise PriceWatchError(f"identity alias {index}: {exc}") from exc
    return ProductIdentityRegistry(aliases)
