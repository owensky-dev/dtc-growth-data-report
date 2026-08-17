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
    def source_frames(self, *, shopify_orders: int, ga4_purchases: int):
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
        shopify = pd.DataFrame(
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
        return ga4, shopify, ads, gsc

    def test_period_summary_persists_shopify_vs_ga4_purchase_gap(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(shopify_orders=3, ga4_purchases=2),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )

        self.assertEqual(summary["ga4_purchases"], 2)
        self.assertEqual(summary["purchase_count_gap"], 1)
        self.assertEqual(summary["purchase_tracking_rate"], 2 / 3)
        self.assertEqual(summary["purchase_revenue_gap"], 100)

    def test_data_health_flags_missing_ga4_purchases_without_auto_recovery(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(shopify_orders=3, ga4_purchases=2),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )
        health = weekly.data_health_rows(
            summary,
            {"sources": {"GSC": {"last_date": "2026-08-16"}}},
            [{"metric": "GA4 开始结账"}],
        )
        integrity = next(row for row in health if row["check"] == "Shopify vs GA4 purchase")

        self.assertEqual(integrity["status"], "高风险")
        self.assertIn("少 1 单", integrity["detail"])
        self.assertIn("BigQuery transaction_id", integrity["detail"])

        actions = weekly.next_action_rows({"current": summary, "funnel": []})
        self.assertEqual(actions[0]["priority"], "P0")
        self.assertIn("核对 Shopify paid order", actions[0]["task"])
        self.assertIn("不在本报告流程自动补发", actions[0]["done"])

    def test_matching_zero_order_week_is_healthy(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(shopify_orders=0, ga4_purchases=0),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )
        health = weekly.data_health_rows(
            summary,
            {"sources": {"GSC": {"last_date": "2026-08-16"}}},
            [{"metric": "GA4 开始结账"}],
        )
        integrity = next(row for row in health if row["check"] == "Shopify vs GA4 purchase")
        self.assertEqual(summary["purchase_tracking_rate"], 1.0)
        self.assertEqual(integrity["status"], "通过")


if __name__ == "__main__":
    unittest.main()
