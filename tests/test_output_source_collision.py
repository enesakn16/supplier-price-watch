"""Regression tests for preventing CLI output from overwriting source data."""

import contextlib
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from supplier_price_watch_cli import main


class OutputSourceCollisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.previous = self.root / "previous.csv"
        self.current = self.root / "current.csv"
        self.previous.write_text(
            "supplier,sku,unit_cost,currency\nDemo,SKU-1,100,TRY\n",
            encoding="utf-8",
        )
        self.current.write_text(
            "supplier,sku,unit_cost,currency\nDemo,SKU-1,110,TRY\n",
            encoding="utf-8",
        )

    def run_cli(self, *options: str) -> tuple[int, str]:
        stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(stderr),
        ):
            status = main([str(self.previous), str(self.current), *options])
        return status, stderr.getvalue()

    def assert_rejected_unchanged(self, output: Path, protected: Path, *options: str) -> None:
        before = protected.read_bytes()
        status, stderr = self.run_cli(*options, "--output", str(output))
        self.assertEqual(status, 2)
        self.assertIn("--output must not overwrite input file", stderr)
        self.assertEqual(protected.read_bytes(), before)
        self.assertEqual(list(self.root.glob(f".{output.name}.*.tmp")), [])

    def test_rejects_direct_previous_and_current_paths(self) -> None:
        for source in (self.previous, self.current):
            with self.subTest(source=source.name):
                self.assert_rejected_unchanged(source, source)

    def test_rejects_optional_source_paths(self) -> None:
        for flag in ("--sales-catalog", "--profile-config", "--identity-map"):
            source = self.root / (flag.removeprefix("--") + ".json")
            source.write_text("original source data\n", encoding="utf-8")
            with self.subTest(flag=flag):
                self.assert_rejected_unchanged(source, source, flag, str(source))

    def test_rejects_symlink_to_input(self) -> None:
        output = self.root / "alias.csv"
        try:
            output.symlink_to(self.previous)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        self.assert_rejected_unchanged(output, self.previous)

    def test_rejects_hardlink_to_input(self) -> None:
        output = self.root / "hardlink.csv"
        try:
            os.link(self.previous, output)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"hardlinks unavailable: {exc}")
        self.assert_rejected_unchanged(output, self.previous)

    def test_distinct_report_still_succeeds(self) -> None:
        output = self.root / "report.csv"
        status, stderr = self.run_cli("--output", str(output))
        self.assertEqual(status, 0, stderr)
        self.assertTrue(output.is_file())
        self.assertIn("matched,Demo,SKU-1,TRY", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
