from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dtc-growth-data-report" / "scripts" / "template"
sys.path.insert(0, str(TEMPLATE_DIR))

import fetch_shopify  # noqa: E402


class ShopifyReportingContractTests(unittest.TestCase):
    def test_order_date_uses_ga4_property_timezone(self) -> None:
        self.assertEqual(
            fetch_shopify.local_order_date(
                "2026-08-09T00:27:17Z", "America/Juneau"
            ),
            "2026-08-08",
        )

    def test_daily_sales_excludes_non_paid_test_and_cancelled_orders(self) -> None:
        rows = [
            {
                "date": "2026-08-08",
                "order_name": "paid",
                "total_price": 100,
                "financial_status": "PAID",
                "test": False,
                "cancelled_at": "",
            },
            {
                "date": "2026-08-08",
                "order_name": "test",
                "total_price": 200,
                "financial_status": "PAID",
                "test": True,
                "cancelled_at": "",
            },
            {
                "date": "2026-08-08",
                "order_name": "cancelled",
                "total_price": 300,
                "financial_status": "PAID",
                "test": False,
                "cancelled_at": "2026-08-09T00:00:00Z",
            },
            {
                "date": "2026-08-08",
                "order_name": "pending",
                "total_price": 400,
                "financial_status": "PENDING",
                "test": False,
                "cancelled_at": "",
            },
        ]

        daily = fetch_shopify.build_daily_sales(
            rows, "2026-08-08", "2026-08-08"
        )

        self.assertEqual(int(daily.loc[0, "orders"]), 1)
        self.assertEqual(float(daily.loc[0, "total_sales"]), 100.0)

    def test_reusable_template_does_not_hardcode_store_timezone(self) -> None:
        source = (TEMPLATE_DIR / "fetch_shopify.py").read_text(encoding="utf-8")
        self.assertIn('settings.get("GA4_PROPERTY_TIMEZONE", "")', source)
        self.assertNotIn('settings.get("GA4_PROPERTY_TIMEZONE", "America/Juneau")', source)

    def test_order_export_preserves_original_and_refunded_amounts(self) -> None:
        self.assertIn("original_total_price", fetch_shopify.COLUMNS)
        self.assertIn("total_refunded", fetch_shopify.COLUMNS)
        self.assertIn("originalTotalPriceSet", fetch_shopify.ORDERS_QUERY)
        self.assertIn("totalRefundedSet", fetch_shopify.ORDERS_QUERY)


if __name__ == "__main__":
    unittest.main()
