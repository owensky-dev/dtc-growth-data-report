from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dtc-growth-data-report" / "scripts" / "template"
sys.path.insert(0, str(TEMPLATE_DIR))

import generate_weekly_comparison_template as weekly  # noqa: E402


class PurchaseIntegrityTests(unittest.TestCase):
    def source_frames(
        self,
        *,
        shopify_orders: int,
        online_store_orders: int,
        ga4_purchases: int,
    ):
        report_date = pd.Timestamp("2026-08-16")
        ga4 = pd.DataFrame(
            [
                {
                    "parsed_date": report_date,
                    "sessions": 100,
                    "ecommercePurchases": ga4_purchases,
                    "totalRevenue": ga4_purchases * 100,
                }
            ]
        )
        order_rows = []
        for index in range(shopify_orders):
            order_rows.append(
                {
                    "parsed_date": report_date,
                    "financial_status": "PAID",
                    "test": False,
                    "cancelled_at": "",
                    "source_name": "web" if index < online_store_orders else "shop-app",
                    "total_price": 100,
                }
            )
        shopify_orders_frame = pd.DataFrame(
            order_rows,
            columns=[
                "parsed_date",
                "financial_status",
                "test",
                "cancelled_at",
                "source_name",
                "total_price",
            ],
        )
        shopify_orders_frame["parsed_date"] = pd.to_datetime(
            shopify_orders_frame["parsed_date"]
        )
        shopify_daily = pd.DataFrame(
            [
                {
                    "parsed_date": report_date,
                    "orders": shopify_orders,
                    "total_sales": shopify_orders * 100,
                }
            ]
        )
        ads = pd.DataFrame([{"parsed_date": report_date}])
        gsc = pd.DataFrame([{"parsed_date": report_date}])
        return ga4, shopify_orders_frame, shopify_daily, ads, gsc

    def test_period_summary_separates_online_store_and_offsite_orders(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(
                shopify_orders=3,
                online_store_orders=2,
                ga4_purchases=1,
            ),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )

        self.assertEqual(summary["orders"], 3)
        self.assertEqual(summary["shopify_online_store_orders"], 2)
        self.assertEqual(summary["shopify_offsite_orders"], 1)
        self.assertEqual(summary["shopify_offsite_revenue"], 100)
        self.assertEqual(summary["ga4_purchases"], 1)
        self.assertEqual(summary["purchase_count_gap"], 1)
        self.assertEqual(summary["purchase_tracking_rate"], 1 / 2)
        self.assertEqual(summary["purchase_revenue_gap"], 100)

    def test_data_health_flags_missing_ga4_purchases_without_auto_recovery(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(
                shopify_orders=3,
                online_store_orders=2,
                ga4_purchases=1,
            ),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )
        health = weekly.data_health_rows(
            summary,
            {"sources": {"GSC": {"last_date": "2026-08-16"}}},
            [{"metric": "GA4 开始结账"}],
        )
        integrity = next(
            row
            for row in health
            if row["check"] == "Shopify Online Store vs GA4 purchase"
        )

        self.assertEqual(integrity["status"], "高风险")
        self.assertIn("Online Store 2 单", integrity["detail"])
        self.assertIn("Shop/其他站外 1 单", integrity["detail"])
        self.assertIn("少 1 单", integrity["detail"])
        self.assertIn("BigQuery transaction_id", integrity["detail"])

        actions = weekly.next_action_rows({"current": summary, "funnel": []})
        self.assertEqual(actions[0]["priority"], "P0")
        self.assertIn("核对 Shopify Online Store paid order", actions[0]["task"])
        self.assertIn("不在本报告流程自动补发", actions[0]["done"])

    def test_matching_zero_order_week_is_healthy(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(
                shopify_orders=0,
                online_store_orders=0,
                ga4_purchases=0,
            ),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )
        health = weekly.data_health_rows(
            summary,
            {"sources": {"GSC": {"last_date": "2026-08-16"}}},
            [{"metric": "GA4 开始结账"}],
        )
        integrity = next(
            row
            for row in health
            if row["check"] == "Shopify Online Store vs GA4 purchase"
        )
        self.assertEqual(summary["purchase_tracking_rate"], 1.0)
        self.assertEqual(integrity["status"], "通过")

    def test_mismatched_order_level_and_daily_shopify_data_fails_closed(self) -> None:
        ga4, order_rows, daily, ads, gsc = self.source_frames(
            shopify_orders=2,
            online_store_orders=2,
            ga4_purchases=1,
        )
        daily.loc[0, "orders"] = 3
        daily.loc[0, "total_sales"] = 300

        with self.assertRaisesRegex(RuntimeError, "do not match"):
            weekly.summarize_period(
                ga4,
                order_rows,
                daily,
                ads,
                gsc,
                date(2026, 8, 16),
                date(2026, 8, 16),
            )

    def test_missing_test_or_cancelled_columns_fail_closed(self) -> None:
        ga4, order_rows, daily, ads, gsc = self.source_frames(
            shopify_orders=1,
            online_store_orders=1,
            ga4_purchases=1,
        )
        order_rows = order_rows.drop(columns=["test", "cancelled_at"])

        with self.assertRaisesRegex(RuntimeError, "cancelled_at.*test"):
            weekly.summarize_period(
                ga4,
                order_rows,
                daily,
                ads,
                gsc,
                date(2026, 8, 16),
                date(2026, 8, 16),
            )


if __name__ == "__main__":
    unittest.main()
