import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from supplier_price_watch_cli import main


class AtomicReportWriteTests(unittest.TestCase):
    def test_replace_failure_preserves_existing_report_and_cleans_temp_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            previous = root / "previous.csv"
            current = root / "current.csv"
            report = root / "report.csv"

            previous.write_text(
                "supplier,sku,unit_cost,currency\nArzu,SKU-1,100,TRY\n",
                encoding="utf-8",
            )
            current.write_text(
                "supplier,sku,unit_cost,currency\nArzu,SKU-1,110,TRY\n",
                encoding="utf-8",
            )
            original_report = "trusted,existing,report\n"
            report.write_text(original_report, encoding="utf-8")

            stderr = io.StringIO()
            with (
                patch(
                    "supplier_price_watch_cli.os.replace",
                    side_effect=OSError("simulated replace failure"),
                ),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = main(
                    [str(previous), str(current), "--output", str(report)]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("cannot write report CSV", stderr.getvalue())
            self.assertEqual(report.read_text(encoding="utf-8"), original_report)
            self.assertEqual(list(root.glob(f".{report.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
