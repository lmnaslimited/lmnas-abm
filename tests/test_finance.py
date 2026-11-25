from decimal import Decimal
import unittest

from abm.domain.finance import normalize_revenue


class FinancialNormalizationTests(unittest.TestCase):
    def test_usd_millions_are_not_converted_twice(self):
        result = normalize_revenue("12.5", "USD", "millions")
        self.assertEqual(result.revenue_usd_m, Decimal("12.5"))
        self.assertEqual(result.reported_amount, Decimal("12.5"))

    def test_non_usd_conversion_retains_provenance(self):
        result = normalize_revenue("2", "EUR", "billions", exchange_rate="1.08",
                                   rate_date="2026-11-24", source="annual report", confidence="High")
        self.assertEqual(result.revenue_usd_m, Decimal("2160.00"))
        self.assertEqual(result.exchange_rate, Decimal("1.08"))
        self.assertEqual(result.source, "annual report")

    def test_unspecified_currency_is_not_assumed_to_be_usd(self):
        result = normalize_revenue("55", None, "millions")
        self.assertIsNone(result.revenue_usd_m)
        self.assertIsNone(result.currency)

    def test_unknown_scale_fails_closed(self):
        with self.assertRaises(ValueError):
            normalize_revenue("55", "USD", "crore")


if __name__ == "__main__":
    unittest.main()
