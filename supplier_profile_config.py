from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from supplier_price_watch import (
    PriceWatchError,
    SupplierImportProfile,
    SupplierProfileRegistry,
)

MAX_PROFILE_CONFIG_BYTES = 256 * 1024
_ALLOWED_KEYS = frozenset({"profile_id", "supplier", "version", "column_map", "sheet_name"})
_REQUIRED_KEYS = frozenset({"profile_id", "supplier", "version", "column_map"})


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PriceWatchError(f"supplier profile config contains duplicate key: {key}")
        result[key] = value
    return result


def _profile_from_mapping(raw: object, *, index: int) -> SupplierImportProfile:
    if not isinstance(raw, dict):
        raise PriceWatchError(f"supplier profile #{index} must be a JSON object")

    unknown = sorted(set(raw).difference(_ALLOWED_KEYS))
    if unknown:
        raise PriceWatchError(
            f"supplier profile #{index} contains unsupported fields: {', '.join(unknown)}"
        )

    missing = sorted(_REQUIRED_KEYS.difference(raw))
    if missing:
        raise PriceWatchError(
            f"supplier profile #{index} missing required fields: {', '.join(missing)}"
        )

    version = raw["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise PriceWatchError(f"supplier profile #{index} version must be an integer")

    column_map = raw["column_map"]
    if not isinstance(column_map, dict):
        raise PriceWatchError(f"supplier profile #{index} column_map must be an object")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in column_map.items()):
        raise PriceWatchError(
            f"supplier profile #{index} column_map keys and values must be strings"
        )

    profile_id = raw["profile_id"]
    supplier = raw["supplier"]
    sheet_name = raw.get("sheet_name")
    if not isinstance(profile_id, str):
        raise PriceWatchError(f"supplier profile #{index} profile_id must be a string")
    if not isinstance(supplier, str):
        raise PriceWatchError(f"supplier profile #{index} supplier must be a string")
    if sheet_name is not None and not isinstance(sheet_name, str):
        raise PriceWatchError(f"supplier profile #{index} sheet_name must be a string or null")

    return SupplierImportProfile(
        profile_id=profile_id,
        supplier=supplier,
        version=version,
        column_map=column_map,
        sheet_name=sheet_name,
    )


def load_profile_registry_json(path: str | Path) -> SupplierProfileRegistry:
    """Load versioned supplier import profiles from a small, strict JSON config.

    The top-level JSON value may be one profile object or an array of profile objects.
    Unknown fields, duplicate JSON keys, malformed types, oversized files and duplicate
    profile/version pairs fail closed instead of being guessed or silently overwritten.
    """

    config_path = Path(path)
    try:
        size = config_path.stat().st_size
    except OSError as exc:
        raise PriceWatchError(f"cannot read supplier profile config: {config_path}") from exc
    if size > MAX_PROFILE_CONFIG_BYTES:
        raise PriceWatchError(
            f"supplier profile config exceeds {MAX_PROFILE_CONFIG_BYTES} bytes"
        )

    try:
        text = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PriceWatchError(f"cannot read supplier profile config: {config_path}") from exc

    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except PriceWatchError:
        raise
    except json.JSONDecodeError as exc:
        raise PriceWatchError(
            f"invalid supplier profile JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc

    items = raw if isinstance(raw, list) else [raw]
    if not items:
        raise PriceWatchError("supplier profile config must contain at least one profile")

    profiles = [
        _profile_from_mapping(item, index=index)
        for index, item in enumerate(items, start=1)
    ]
    return SupplierProfileRegistry(profiles)
