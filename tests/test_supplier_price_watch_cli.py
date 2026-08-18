import argparse
import contextlib
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook

from supplier_price_watch import PriceWatchError
from supplier_price_watch_cli import _resolve_profile, main


class SupplierPriceWatchCliProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _write_profiles(self) -> Path:
        path = self.root / "profiles.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "profile_id": "arzu",
                        "supplier": "Arzu",
                        "version": 1,
                        "column_map": {
                            "Kod": "sku",
                            "Fiyat": "unit_cost",
                            "Doviz": "currency",
                        },
                    },
                    {
                        "profile_id": "arzu",
                        "supplier": "Arzu",
                        "version": 2,
                        "column_map": {
                            "Urun Kodu": "sku",
                            "Net Fiyat": "unit_cost",
                            "Para Birimi": "currency",
                        },
                        "sheet_name": "Fiyat Listesi",
                    },
                ]
            ),
            encoding="utf-8",
        )
        return path

    def _args(
        self,
        *,
        profile_config: Path | None,
        profile_id: str | None,
        profile_version: int | None = None,
    ) -> argparse.Namespace:
        return argparse.Namespace(
            profile_config=profile_config,
            profile_id=profile_id,
            profile_version=profile_version,
        )

    def test_profile_flags_must_be_supplied_together(self) -> None:
        with self.assertRaisesRegex(
            PriceWatchError,
            "--profile-config and --profile-id must be provided together",
        ):
            _resolve_profile(
                self._args(
                    profile_config=self._write_profiles(),
                    profile_id=None,
                )
            )

        with self.assertRaisesRegex(
            PriceWatchError,
            "--profile-config and --profile-id must be provided together",
        ):
            _resolve_profile(
                self._args(
                    profile_config=None,
                    profile_id="arzu",
                )
            )

    def test_profile_resolution_uses_latest_or_exact_version(self) -> None:
        config = self._write_profiles()

        latest = _resolve_profile(
            self._args(profile_config=config, profile_id="arzu")
        )
        exact = _resolve_profile(
            self._args(
                profile_config=config,
                profile_id="arzu",
                profile_version=1,
            )
        )

        self.assertIsNotNone(latest)
        self.assertIsNotNone(exact)
        self.assertEqual(latest.version, 2)
        self.assertEqual(exact.version, 1)
        self.assertEqual(latest.column_map["Net Fiyat"], "unit_cost")
        self.assertEqual(exact.column_map["Fiyat"], "unit_cost")

    def test_unknown_profile_id_returns_exit_code_2(self) -> None:
        config = self._write_profiles()
        previous = self.root / "previous.csv"
        current = self.root / "current.csv"
        previous.write_text("Kod,Fiyat,Doviz\nSKU-1,100,TRY\n", encoding="utf-8")
        current.write_text("Kod,Fiyat,Doviz\nSKU-1,110,TRY\n", encoding="utf-8")

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    str(previous),
                    str(current),
                    "--profile-config",
                    str(config),
                    "--profile-id",
                    "missing",
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("not found", stderr.getvalue())

    def test_csv_cli_uses_exact_supplier_profile(self) -> None:
        config = self._write_profiles()
        previous = self.root / "previous.csv"
        current = self.root / "current.csv"
        previous.write_text("Kod,Fiyat,Doviz\nSKU-1,100,TRY\n", encoding="utf-8")
        current.write_text("Kod,Fiyat,Doviz\nSKU-1,115,TRY\n", encoding="utf-8")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    str(previous),
                    str(current),
                    "--profile-config",
                    str(config),
                    "--profile-id",
                    "arzu",
                    "--profile-version",
                    "1",
                ]
            )

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Arzu", output)
        self.assertIn("SKU-1", output)
        self.assertIn("15.00", output)

    def test_csv_cli_reports_added_and_removed_catalog_rows(self) -> None:
        config = self._write_profiles()
        previous = self.root / "previous.csv"
        current = self.root / "current.csv"
        report = self.root / "report.csv"
        previous.write_text(
            "Kod,Fiyat,Doviz\nSKU-KEEP,100,TRY\nSKU-OLD,50,TRY\n",
            encoding="utf-8",
        )
        current.write_text(
            "Kod,Fiyat,Doviz\nSKU-KEEP,110,TRY\nSKU-NEW,70,TRY\n",
            encoding="utf-8",
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    str(previous),
                    str(current),
                    "--profile-config",
                    str(config),
                    "--profile-id",
                    "arzu",
                    "--profile-version",
                    "1",
                    "--output",
                    str(report),
                ]
            )

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("+ ADDED    Arzu | SKU-NEW | 70.00 TRY", output)
        self.assertIn("- REMOVED  Arzu | SKU-OLD | 50.00 TRY", output)

        with report.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        by_status = {row["status"]: row for row in rows}
        self.assertEqual(set(by_status), {"matched", "added", "removed"})
        self.assertEqual(by_status["added"]["sku"], "SKU-NEW")
        self.assertEqual(by_status["added"]["current_cost"], "70.00")
        self.assertEqual(by_status["added"]["currency"], "TRY")
        self.assertEqual(by_status["removed"]["sku"], "SKU-OLD")
        self.assertEqual(by_status["removed"]["previous_cost"], "50.00")
        self.assertEqual(by_status["removed"]["currency"], "TRY")

    def test_xlsx_cli_uses_latest_profile_and_declared_sheet(self) -> None:
        config = self._write_profiles()
        previous = self.root / "previous.xlsx"
        current = self.root / "current.xlsx"

        for path, price in ((previous, 80), (current, 92)):
            workbook = Workbook()
            ignored = workbook.active
            ignored.title = "Ignore"
            ignored.append(["wrong"])
            ignored.append(["data"])
            sheet = workbook.create_sheet("Fiyat Listesi")
            sheet.append(["Urun Kodu", "Net Fiyat", "Para Birimi"])
            sheet.append(["SKU-X", price, "TRY"])
            workbook.save(path)
            workbook.close()

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    str(previous),
                    str(current),
                    "--profile-config",
                    str(config),
                    "--profile-id",
                    "arzu",
                ]
            )

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Arzu", output)
        self.assertIn("SKU-X", output)
        self.assertIn("15.00", output)


if __name__ == "__main__":
    unittest.main()
