from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dtc-growth-data-report" / "scripts" / "template"
sys.path.insert(0, str(TEMPLATE_DIR))

import fetch_google_ads  # noqa: E402
import generate_weekly_comparison_template as weekly  # noqa: E402


class GoogleAdsCampaignCoverageTests(unittest.TestCase):
    def test_campaign_fetch_includes_performance_max_metrics(self) -> None:
        item = SimpleNamespace(
            segments=SimpleNamespace(date="2026-08-01"),
            campaign=SimpleNamespace(
                id=23799806631,
                name="COZY-US-2026.04",
                status=SimpleNamespace(name="ENABLED"),
                advertising_channel_type=SimpleNamespace(name="PERFORMANCE_MAX"),
            ),
            metrics=SimpleNamespace(
                impressions=4364,
                clicks=45,
                cost_micros=142_593_308,
                conversions=6,
                conversions_value=2204.98,
                all_conversions=191.166666,
                all_conversions_value=8873.246666,
            ),
        )
        with patch.object(
            fetch_google_ads,
            "stream_query",
            return_value=[SimpleNamespace(results=[item])],
        ):
            rows = fetch_google_ads.fetch_campaign_performance(
                object(), "1234567890", "2026-07-26", "2026-08-01"
            )

        self.assertEqual(rows[0]["campaign_type"], "PERFORMANCE_MAX")
        self.assertEqual(rows[0]["conversions"], 6.0)
        self.assertEqual(rows[0]["conversion_value"], 2204.98)

    def test_weekly_campaign_rows_include_pmax_without_ad_group(self) -> None:
        ads = pd.DataFrame(
            [
                {
                    "parsed_date": pd.Timestamp("2026-08-01"),
                    "campaign_name": "COZY-US-2026.04",
                    "cost": 142.593308,
                    "clicks": 45,
                    "conversions": 6,
                    "conversion_value": 2204.98,
                }
            ]
        )

        rows = weekly.ads_rows(ads, date(2026, 7, 26), date(2026, 8, 1))

        self.assertEqual(rows[0]["campaign"], "COZY-US-2026.04")
        self.assertEqual(rows[0]["ad_group"], "系列级")
        self.assertEqual(rows[0]["conversions"], "6")
        self.assertEqual(rows[0]["roas"], "15.46")


if __name__ == "__main__":
    unittest.main()
