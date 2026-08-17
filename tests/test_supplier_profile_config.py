import json
import tempfile
import unittest
from pathlib import Path

from supplier_price_watch import PriceWatchError
from supplier_profile_config import load_profile_registry_json


class SupplierProfileConfigTests(unittest.TestCase):
    def _write(self, content: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "profiles.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_single_profile_object(self) -> None:
        path = self._write(json.dumps({
            "profile_id": "arzu-price-list",
            "supplier": "Arzu",
            "version": 1,
            "column_map": {"Urun Kodu": "sku", "Alis Fiyati": "unit_cost"},
            "sheet_name": "Fiyat Listesi",
        }))

        registry = load_profile_registry_json(path)
        profile = registry.get("arzu-price-list")

        self.assertEqual(profile.supplier, "Arzu")
        self.assertEqual(profile.version, 1)
        self.assertEqual(profile.column_map["Urun Kodu"], "sku")
        self.assertEqual(profile.sheet_name, "Fiyat Listesi")

    def test_loads_multiple_versions_and_resolves_latest(self) -> None:
        path = self._write(json.dumps([
            {
                "profile_id": "msr",
                "supplier": "MSR",
                "version": 1,
                "column_map": {"Kod": "sku", "Fiyat": "unit_cost"},
            },
            {
                "profile_id": "msr",
                "supplier": "MSR",
                "version": 2,
                "column_map": {"Stok Kodu": "sku", "Net Fiyat": "unit_cost"},
            },
        ]))

        registry = load_profile_registry_json(path)

        self.assertEqual(registry.get("msr").version, 2)
        self.assertEqual(registry.get("msr", version=1).version, 1)

    def test_rejects_duplicate_json_keys(self) -> None:
        path = self._write(
            '{"profile_id":"konar","profile_id":"other","supplier":"Konar",'
            '"version":1,"column_map":{"Kod":"sku","Fiyat":"unit_cost"}}'
        )

        with self.assertRaisesRegex(PriceWatchError, "duplicate key: profile_id"):
            load_profile_registry_json(path)

    def test_rejects_unknown_fields(self) -> None:
        path = self._write(json.dumps({
            "profile_id": "konar",
            "supplier": "Konar",
            "version": 1,
            "column_map": {"Kod": "sku", "Fiyat": "unit_cost"},
            "auto_detect": True,
        }))

        with self.assertRaisesRegex(PriceWatchError, "unsupported fields: auto_detect"):
            load_profile_registry_json(path)

    def test_rejects_duplicate_profile_version(self) -> None:
        profile = {
            "profile_id": "arzu",
            "supplier": "Arzu",
            "version": 1,
            "column_map": {"Kod": "sku", "Fiyat": "unit_cost"},
        }
        path = self._write(json.dumps([profile, profile]))

        with self.assertRaisesRegex(PriceWatchError, "duplicate supplier profile/version"):
            load_profile_registry_json(path)

    def test_rejects_non_integer_version(self) -> None:
        path = self._write(json.dumps({
            "profile_id": "arzu",
            "supplier": "Arzu",
            "version": "1",
            "column_map": {"Kod": "sku", "Fiyat": "unit_cost"},
        }))

        with self.assertRaisesRegex(PriceWatchError, "version must be an integer"):
            load_profile_registry_json(path)

    def test_rejects_empty_profile_array(self) -> None:
        path = self._write("[]")

        with self.assertRaisesRegex(PriceWatchError, "at least one profile"):
            load_profile_registry_json(path)


if __name__ == "__main__":
    unittest.main()
