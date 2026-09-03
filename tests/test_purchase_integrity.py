from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dtc-growth-data-report" / "scripts" / "template"
sys.path.insert(0, str(TEMPLATE_DIR))

import generate_weekly_comparison_template as weekly  # noqa: E402


class PurchaseIntegrityTests(unittest.TestCase):
    def reconciliation_payload(
        self,
        *,
        current_paid_orders: int,
        current_paid_revenue: float,
        eligible: int,
        matched: int,
        missing: int,
        refund_expected: int = 0,
        refund_matched: int = 0,
        refund_missing: int = 0,
        publishable: bool = True,
    ):
        return {
            "schema_version": "1.0",
            "period": {"start_date": "2026-08-16", "end_date": "2026-08-16"},
            "coverage": {"status": "complete" if publishable else "incomplete"},
            "shopify": {
                "current_paid_web": {
                    "orders": current_paid_orders,
                    "revenue": current_paid_revenue,
                }
            },
            "ga4": {
                "purchase": {
                    "duplicate_transaction_ids": [],
                    "blank_transaction_id_events": 0,
                }
            },
            "reconciliation": {
                "status": "exceptions" if missing or refund_missing else "matched",
                "publishable": publishable,
                "purchase": {
                    "eligible_web_transactions": eligible,
                    "matched_web_transactions": matched,
                    "capture_rate": matched / eligible if publishable and eligible else (1.0 if publishable else None),
                    "missing_web_transactions": missing,
                    "ga4_only_transactions": 0,
                    "current_paid_web_coverage_rate": matched / current_paid_orders if publishable and current_paid_orders else (1.0 if publishable else None),
                },
                "refund": {
                    "expected_transactions": refund_expected,
                    "matched_transactions": refund_matched,
                    "missing_transactions": refund_missing,
                    "capture_rate": refund_matched / refund_expected if publishable and refund_expected else (1.0 if publishable else None),
                },
                "amount_bridge": {
                    "aggregate_revenue_gap": current_paid_revenue - matched * 100,
                    "current_paid_shopify_only_revenue": max(current_paid_orders - matched, 0) * 100,
                    "ga4_not_current_paid_revenue": 0,
                    "unexplained_revenue_gap": 0,
                },
            },
        }

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
        self.assertEqual(summary["aggregate_purchase_count_gap"], 1)
        self.assertEqual(summary["aggregate_purchase_ratio"], 1 / 2)
        self.assertEqual(summary["aggregate_purchase_revenue_gap"], 100)
        self.assertNotIn("purchase_tracking_rate", summary)

    def test_data_health_keeps_aggregate_gap_as_unverified_alert(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(
                shopify_orders=3,
                online_store_orders=2,
                ga4_purchases=1,
            ),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )
        weekly.apply_purchase_reconciliation(
            summary,
            None,
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

        self.assertEqual(integrity["status"], "待核对")
        self.assertIn("Online Store 2 单", integrity["detail"])
        self.assertIn("Shop/其他站外 1 单", integrity["detail"])
        self.assertIn("该比值不是追踪率", integrity["detail"])

        actions = weekly.next_action_rows({"current": summary, "funnel": []})
        self.assertEqual(actions[0]["priority"], "P0")
        self.assertIn("核对 Shopify Online Store paid order", actions[0]["task"])
        self.assertIn("不发布追踪率", actions[0]["done"])

    def test_verified_reconciliation_reports_purchase_and_refund_separately(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(shopify_orders=3, online_store_orders=2, ga4_purchases=1),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )
        payload = self.reconciliation_payload(
            current_paid_orders=2,
            current_paid_revenue=200,
            eligible=3,
            matched=1,
            missing=2,
            refund_expected=1,
            refund_missing=1,
        )
        weekly.apply_purchase_reconciliation(summary, payload, date(2026, 8, 16), date(2026, 8, 16))
        health = weekly.data_health_rows(
            summary,
            {"sources": {"GSC": {"last_date": "2026-08-16"}}},
            [{"metric": "GA4 开始结账"}],
        )
        integrity = next(row for row in health if row["check"] == "Shopify Online Store vs GA4 purchase")

        self.assertEqual(integrity["status"], "高风险")
        self.assertIn("网页 purchase 捕获 1/3", integrity["detail"])
        self.assertIn("捕获率 33.33%", integrity["detail"])
        self.assertIn("退款回传 0/1", integrity["detail"])

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
        weekly.apply_purchase_reconciliation(
            summary,
            self.reconciliation_payload(
                current_paid_orders=0,
                current_paid_revenue=0,
                eligible=0,
                matched=0,
                missing=0,
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
        self.assertEqual(summary["purchase_reconciliation"]["purchase_capture_rate"], 1.0)
        self.assertEqual(integrity["status"], "通过")

    def test_incomplete_or_stale_reconciliation_suppresses_rate(self) -> None:
        summary = weekly.summarize_period(
            *self.source_frames(shopify_orders=1, online_store_orders=1, ga4_purchases=1),
            date(2026, 8, 16),
            date(2026, 8, 16),
        )
        payload = self.reconciliation_payload(
            current_paid_orders=1,
            current_paid_revenue=100,
            eligible=1,
            matched=1,
            missing=0,
            publishable=False,
        )
        weekly.apply_purchase_reconciliation(summary, payload, date(2026, 8, 16), date(2026, 8, 16))
        self.assertFalse(summary["purchase_reconciliation"]["publishable"])
        self.assertIsNone(summary["purchase_reconciliation"]["purchase_capture_rate"])

        payload["reconciliation"]["publishable"] = True
        weekly.apply_purchase_reconciliation(summary, payload, date(2026, 8, 16), date(2026, 8, 16))
        self.assertEqual(summary["purchase_reconciliation"]["status"], "incomplete_bigquery_coverage")
        self.assertFalse(summary["purchase_reconciliation"]["publishable"])
        self.assertIsNone(summary["purchase_reconciliation"]["purchase_capture_rate"])

        payload["period"]["end_date"] = "2026-08-15"
        weekly.apply_purchase_reconciliation(summary, payload, date(2026, 8, 16), date(2026, 8, 16))
        self.assertEqual(summary["purchase_reconciliation"]["status"], "period_mismatch")

    def test_loader_rejects_unknown_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reconciliation.json"
            path.write_text(json.dumps({"schema_version": "2.0"}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Unsupported purchase reconciliation contract"):
                weekly.load_purchase_reconciliation(path)

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
