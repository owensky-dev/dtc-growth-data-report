from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dtc-growth-data-report" / "scripts" / "template"
sys.path.insert(0, str(TEMPLATE_DIR))

import fetch_shopify  # noqa: E402
import generate_weekly_comparison_template as weekly  # noqa: E402


class WeeklyRoiTests(unittest.TestCase):
    def test_sitewide_roi_and_gsc_clicks_are_persisted(self) -> None:
        report_date = pd.Timestamp("2026-07-13")
        ga4 = pd.DataFrame([{"parsed_date": report_date, "sessions": 100}])
        shopify = pd.DataFrame(
            [{"parsed_date": report_date, "orders": 2, "total_sales": 300}]
        )
        ads = pd.DataFrame(
            [
                {
                    "parsed_date": report_date,
                    "cost": 100,
                    "clicks": 25,
                    "conversions": 1,
                    "conversion_value": 120,
                }
            ]
        )
        gsc = pd.DataFrame(
            [
                {
                    "parsed_date": report_date,
                    "clicks": 12,
                    "impressions": 600,
                    "position": 8,
                }
            ]
        )

        summary = weekly.summarize_period(
            ga4, shopify, ads, gsc, date(2026, 7, 13), date(2026, 7, 13)
        )

        self.assertEqual(summary["site_roi"], 3.0)
        rows = weekly.kpi_rows(summary, summary)
        gsc_clicks = next(row for row in rows if row["metric"] == "GSC 点击数")
        self.assertEqual(gsc_clicks["current"], "12")

        source = (TEMPLATE_DIR / "generate_weekly_comparison_template.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('(\"整站 ROI\", f\"{data[\'current\'][\'site_roi\']:.2f}\"', source)
        self.assertIn("grid-template-columns: repeat(5", source)


class ShopifyClientCredentialsTests(unittest.TestCase):
    @patch.object(fetch_shopify.requests, "post")
    def test_client_credentials_exchange_returns_access_token(self, post: Mock) -> None:
        response = Mock()
        response.json.return_value = {"access_token": "short-lived-token"}
        post.return_value = response

        token = fetch_shopify.client_credentials_token(
            "brand.myshopify.com", "client-id", "client-secret"
        )

        self.assertEqual(token, "short-lived-token")
        response.raise_for_status.assert_called_once_with()
        post.assert_called_once()
        request = post.call_args.kwargs
        self.assertEqual(request["data"]["grant_type"], "client_credentials")


if __name__ == "__main__":
    unittest.main()
