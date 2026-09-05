import contextlib
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from supplier_price_watch_cli import main


class CliIdentityMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_supplier_sku_change_is_compared_via_canonical_identity(self) -> None:
        previous = self.root / "previous.csv"
        current = self.root / "current.csv"
        identity_map = self.root / "identity-map.json"
        sales_catalog = self.root / "sales.csv"
        report = self.root / "report.csv"

        previous.write_text(
            "supplier,sku,unit_cost,currency\n"
            "Arzu,ARZ-OLD-42,90,TRY\n",
            encoding="utf-8",
        )
        current.write_text(
            "supplier,sku,unit_cost,currency\n"
            "Arzu,ARZ-NEW-42,95,TRY\n",
            encoding="utf-8",
        )
        identity_map.write_text(
            json.dumps(
                [
                    {
                        "supplier": "Arzu",
                        "source_sku": "ARZ-OLD-42",
                        "canonical_sku": "PCX-ARKA-BALATA-01",
                    },
                    {
                        "supplier": "Arzu",
                        "source_sku": "ARZ-NEW-42",
                        "canonical_sku": "PCX-ARKA-BALATA-01",
                    },
                ]
            ),
            encoding="utf-8",
        )
        sales_catalog.write_text(
            "sku,sale_price,currency\n"
            "PCX-ARKA-BALATA-01,100,TRY\n",
            encoding="utf-8",
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    str(previous),
                    str(current),
                    "--identity-map",
                    str(identity_map),
                    "--sales-catalog",
                    str(sales_catalog),
                    "--output",
                    str(report),
                ]
            )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("matched=1", output)
        self.assertIn("added=0", output)
        self.assertIn("removed=0", output)
        self.assertIn("PCX-ARKA-BALATA-01", output)
        self.assertNotIn("ARZ-OLD-42", output)
        self.assertNotIn("ARZ-NEW-42", output)
        self.assertIn("5.00", output)
        self.assertIn("critical", output)

        with report.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["status"], "matched")
        self.assertEqual(row["supplier"], "Arzu")
        self.assertEqual(row["sku"], "PCX-ARKA-BALATA-01")
        self.assertEqual(row["currency"], "TRY")
        self.assertEqual(row["previous_cost"], "90.00")
        self.assertEqual(row["current_cost"], "95.00")
        self.assertEqual(row["gross_margin_percent"], "5.00")
        self.assertEqual(row["risk"], "critical")


if __name__ == "__main__":
    unittest.main()
