from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dtc-growth-data-report" / "scripts" / "template"
sys.path.insert(0, str(TEMPLATE_DIR))

import fetch_gsc  # noqa: E402
import generate_weekly_comparison_template as weekly  # noqa: E402


class GscPropertyTotalsTests(unittest.TestCase):
    @patch.object(fetch_gsc.service_account.Credentials, "from_service_account_file")
    @patch.object(fetch_gsc, "build")
    def test_daily_request_uses_property_aggregation(
        self, build: Mock, credentials: Mock
    ) -> None:
        credentials.return_value = object()
        query = Mock()
        query.execute.return_value = {
            "rows": [
                {
                    "keys": ["2026-08-22"],
                    "clicks": 44,
                    "impressions": 4854,
                    "ctr": 44 / 4854,
                    "position": 38.65,
                }
            ]
        }
        service = Mock()
        service.searchanalytics.return_value.query.return_value = query
        build.return_value = service

        rows = fetch_gsc.fetch_gsc_rows(
            "service-account.json",
            "sc-domain:example.com",
            "2026-08-22",
            "2026-08-22",
            dimensions=["date"],
            aggregation_type="byProperty",
        )

        body = service.searchanalytics.return_value.query.call_args.kwargs["body"]
        self.assertEqual(body["dimensions"], ["date"])
        self.assertEqual(body["aggregationType"], "byProperty")
        self.assertEqual(body["type"], "web")
        self.assertEqual(rows[0]["clicks"], 44)

    def test_weekly_site_kpis_keep_property_totals(self) -> None:
        report_date = pd.Timestamp("2026-08-22")
        empty_orders = pd.DataFrame(
            {
                "parsed_date": pd.Series(dtype="datetime64[ns]"),
                "financial_status": pd.Series(dtype="object"),
                "test": pd.Series(dtype="bool"),
                "cancelled_at": pd.Series(dtype="object"),
                "source_name": pd.Series(dtype="object"),
                "total_price": pd.Series(dtype="float64"),
            }
        )
        summary = weekly.summarize_period(
            pd.DataFrame(
                [
                    {
                        "parsed_date": report_date,
                        "sessions": 100,
                        "ecommercePurchases": 0,
                        "totalRevenue": 0,
                    }
                ]
            ),
            empty_orders,
            pd.DataFrame(
                [{"parsed_date": report_date, "orders": 0, "total_sales": 0}]
            ),
            pd.DataFrame([{"parsed_date": report_date}]),
            pd.DataFrame(
                [
                    {
                        "parsed_date": report_date,
                        "clicks": 44,
                        "impressions": 4854,
                        "position": 38.65,
                    }
                ]
            ),
            date(2026, 8, 22),
            date(2026, 8, 22),
        )

        self.assertEqual(summary["seo_clicks"], 44)
        self.assertEqual(summary["seo_impressions"], 4854)
        self.assertAlmostEqual(summary["seo_ctr"], 44 / 4854)

        source = (TEMPLATE_DIR / "generate_weekly_comparison_template.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('read_csv(DATA_RAW_DIR / "gsc_daily_90d.csv")', source)
        self.assertIn('seo_rows(sources["gsc_detail"]', source)


if __name__ == "__main__":
    unittest.main()
