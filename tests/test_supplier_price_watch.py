from decimal import Decimal
import unittest

from supplier_price_watch import (
    PriceWatchError,
    RiskLevel,
    SupplierQuote,
    compare_catalogs,
    compare_quote,
)


class SupplierQuoteTests(unittest.TestCase):
    def test_from_mapping_normalizes_currency_and_money(self):
        quote = SupplierQuote.from_mapping(
            {
                "supplier": "  Arzu Bisiklet  ",
                "sku": " SKU-001 ",
                "unit_cost": "123.455",
                "currency": "try",
            }
        )

        self.assertEqual(quote.supplier, "Arzu Bisiklet")
        self.assertEqual(quote.sku, "SKU-001")
        self.assertEqual(quote.unit_cost, Decimal("123.46"))
        self.assertEqual(quote.currency, "TRY")

    def test_negative_cost_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "cannot be negative"):
            SupplierQuote.from_mapping(
                {"supplier": "S", "sku": "A", "unit_cost": "-1"}
            )

    def test_invalid_currency_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "3-letter code"):
            SupplierQuote.from_mapping(
                {
                    "supplier": "S",
                    "sku": "A",
                    "unit_cost": "10",
                    "currency": "TL",
                }
            )


class PriceComparisonTests(unittest.TestCase):
    def quote(self, cost: str, *, sku: str = "SKU-1", currency: str = "TRY"):
        return SupplierQuote.from_mapping(
            {
                "supplier": "Supplier A",
                "sku": sku,
                "unit_cost": cost,
                "currency": currency,
            }
        )

    def test_price_change_and_rounding_use_decimal_math(self):
        result = compare_quote(self.quote("100.00"), self.quote("112.345"))

        self.assertEqual(result.current_cost, Decimal("112.35"))
        self.assertEqual(result.absolute_change, Decimal("12.35"))
        self.assertEqual(result.percent_change, Decimal("12.35"))

    def test_zero_previous_cost_has_no_percent_change(self):
        result = compare_quote(self.quote("0"), self.quote("25"))

        self.assertIsNone(result.percent_change)
        self.assertEqual(result.absolute_change, Decimal("25.00"))

    def test_currency_mismatch_fails_closed(self):
        with self.assertRaisesRegex(PriceWatchError, "currency mismatch"):
            compare_quote(self.quote("100", currency="TRY"), self.quote("100", currency="USD"))

    def test_critical_margin_boundary_is_inclusive(self):
        result = compare_quote(
            self.quote("80"),
            self.quote("90"),
            sale_price="100",
            warning_margin_percent="20",
            critical_margin_percent="10",
        )

        self.assertEqual(result.gross_margin_percent, Decimal("10.00"))
        self.assertEqual(result.risk, RiskLevel.CRITICAL)

    def test_warning_margin_boundary_is_inclusive(self):
        result = compare_quote(
            self.quote("70"),
            self.quote("80"),
            sale_price="100",
            warning_margin_percent="20",
            critical_margin_percent="10",
        )

        self.assertEqual(result.gross_margin_percent, Decimal("20.00"))
        self.assertEqual(result.risk, RiskLevel.WARNING)

    def test_invalid_threshold_order_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "cannot exceed warning"):
            compare_quote(
                self.quote("70"),
                self.quote("80"),
                sale_price="100",
                warning_margin_percent="10",
                critical_margin_percent="20",
            )

    def test_zero_sale_price_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "greater than zero"):
            compare_quote(self.quote("70"), self.quote("80"), sale_price="0")


class CatalogComparisonTests(unittest.TestCase):
    def test_catalog_comparison_matches_exact_supplier_sku_currency_only(self):
        previous = [
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "MATCH", "unit_cost": "100", "currency": "TRY"}
            ),
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "OLD", "unit_cost": "50", "currency": "TRY"}
            ),
        ]
        current = [
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "MATCH", "unit_cost": "110", "currency": "TRY"}
            ),
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "NEW", "unit_cost": "55", "currency": "TRY"}
            ),
        ]

        results = compare_catalogs(previous, current, sale_prices={"MATCH": "150"})

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].sku, "MATCH")
        self.assertEqual(results[0].gross_margin_percent, Decimal("26.67"))
        self.assertEqual(results[0].risk, RiskLevel.OK)


if __name__ == "__main__":
    unittest.main()
