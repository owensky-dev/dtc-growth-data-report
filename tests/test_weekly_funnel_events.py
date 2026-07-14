from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dtc-growth-data-report" / "scripts" / "template"
sys.path.insert(0, str(TEMPLATE_DIR))

import generate_weekly_comparison_template as weekly  # noqa: E402


class WeeklyFunnelEventTests(unittest.TestCase):
    def test_funnel_uses_dated_add_to_cart_and_begin_checkout(self) -> None:
        events = pd.DataFrame(
            [
                {"parsed_date": pd.Timestamp("2026-07-01"), "eventName": "add_to_cart", "eventCount": 4},
                {"parsed_date": pd.Timestamp("2026-07-02"), "eventName": "begin_checkout", "eventCount": 2},
                {"parsed_date": pd.Timestamp("2026-07-08"), "eventName": "add_to_cart", "eventCount": 10},
                {"parsed_date": pd.Timestamp("2026-07-09"), "eventName": "begin_checkout", "eventCount": 5},
            ]
        )
        current = {"sessions": 100, "orders": 2, "conversion_rate": 0.02, "ad_clicks": 20, "ad_conversions": 1}
        previous = {"sessions": 80, "orders": 1, "conversion_rate": 0.0125, "ad_clicks": 10, "ad_conversions": 1}

        rows = weekly.funnel_rows(
            current,
            previous,
            pd.DataFrame(),
            events,
            date(2026, 7, 7),
            date(2026, 7, 13),
            date(2026, 6, 30),
            date(2026, 7, 6),
        )

        add_to_cart = next(row for row in rows if row["metric"] == "GA4 加购")
        checkout = next(row for row in rows if row["metric"] == "GA4 开始结账")
        self.assertEqual(add_to_cart["current"], "10")
        self.assertEqual(add_to_cart["previous"], "4")
        self.assertEqual(add_to_cart["rate"], "10.00%")
        self.assertEqual(checkout["current"], "5")
        self.assertEqual(checkout["previous"], "2")
        self.assertEqual(checkout["rate"], "50.00%")

        health = weekly.data_health_rows(
            {"ad_value": 0, "revenue": 0, "orders": 0},
            {"sources": {"GSC": {"last_date": "2026-07-13"}}},
            rows,
        )
        funnel_check = next(row for row in health if row["check"] == "GA4 周度漏斗")
        self.assertEqual(funnel_check["status"], "通过")

        actions = weekly.next_action_rows({"funnel": rows})
        self.assertFalse(any("补齐 GA4" in row["task"] for row in actions))


if __name__ == "__main__":
    unittest.main()
