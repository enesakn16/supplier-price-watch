import contextlib
import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from supplier_price_watch_cli import main


class CliMarginRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _write_quotes(self) -> tuple[Path, Path]:
        previous = self.root / "previous.csv"
        current = self.root / "current.csv"
        previous.write_text(
            "supplier,sku,unit_cost,currency\n"
            "Arzu,SKU-CRITICAL,90,TRY\n"
            "Arzu,SKU-WARNING,80,TRY\n"
            "Arzu,SKU-OK,60,TRY\n",
            encoding="utf-8",
        )
        current.write_text(
            "supplier,sku,unit_cost,currency\n"
            "Arzu,SKU-CRITICAL,95,TRY\n"
            "Arzu,SKU-WARNING,85,TRY\n"
            "Arzu,SKU-OK,70,TRY\n",
            encoding="utf-8",
        )
        return previous, current

    def _write_sales_catalog(self, *, currency: str = "TRY") -> Path:
        catalog = self.root / "sales.csv"
        catalog.write_text(
            "sku,sale_price,currency\n"
            f"SKU-CRITICAL,100,{currency}\n"
            f"SKU-WARNING,100,{currency}\n"
            f"SKU-OK,100,{currency}\n",
            encoding="utf-8",
        )
        return catalog

    def test_cli_reports_margin_and_risk_to_terminal_and_csv(self) -> None:
        previous, current = self._write_quotes()
        sales = self._write_sales_catalog()
        report = self.root / "report.csv"

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    str(previous),
                    str(current),
                    "--sales-catalog",
                    str(sales),
                    "--output",
                    str(report),
                ]
            )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("SKU-CRITICAL", output)
        self.assertIn("5.00", output)
        self.assertIn("critical", output)
        self.assertIn("SKU-WARNING", output)
        self.assertIn("15.00", output)
        self.assertIn("warning", output)
        self.assertIn("SKU-OK", output)
        self.assertIn("30.00", output)
        self.assertIn("ok", output)

        with report.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        by_sku = {row["sku"]: row for row in rows}
        self.assertEqual(by_sku["SKU-CRITICAL"]["gross_margin_percent"], "5.00")
        self.assertEqual(by_sku["SKU-CRITICAL"]["risk"], "critical")
        self.assertEqual(by_sku["SKU-WARNING"]["gross_margin_percent"], "15.00")
        self.assertEqual(by_sku["SKU-WARNING"]["risk"], "warning")
        self.assertEqual(by_sku["SKU-OK"]["gross_margin_percent"], "30.00")
        self.assertEqual(by_sku["SKU-OK"]["risk"], "ok")

    def test_only_risk_requires_sales_catalog(self) -> None:
        previous, current = self._write_quotes()

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main([str(previous), str(current), "--only-risk"])

        self.assertEqual(exit_code, 2)
        self.assertIn("--only-risk requires --sales-catalog", stderr.getvalue())

    def test_only_risk_filters_ok_rows(self) -> None:
        previous, current = self._write_quotes()
        sales = self._write_sales_catalog()

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    str(previous),
                    str(current),
                    "--sales-catalog",
                    str(sales),
                    "--only-risk",
                ]
            )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("SKU-CRITICAL", output)
        self.assertIn("SKU-WARNING", output)
        self.assertNotIn("SKU-OK", output)

    def test_sales_catalog_currency_mismatch_fails_closed(self) -> None:
        previous, current = self._write_quotes()
        sales = self._write_sales_catalog(currency="USD")

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(
                [str(previous), str(current), "--sales-catalog", str(sales)]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("sales catalog currency mismatch", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
