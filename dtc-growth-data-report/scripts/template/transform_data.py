from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config import DATA_PROCESSED_DIR, DATA_RAW_DIR, ensure_dirs, normalize_url, setup_logging


LOGGER = setup_logging("transform_data")


def read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        LOGGER.warning("Missing raw file: %s", path)
        return pd.DataFrame(columns=columns or [])
    frame = pd.read_csv(path)
    LOGGER.info("Loaded %s rows=%s", path.name, len(frame))
    return frame


def numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return frame


def safe_divide(numerator, denominator):
    numerator = pd.to_numeric(numerator, errors="coerce").fillna(0)
    denominator = pd.to_numeric(denominator, errors="coerce").fillna(0)
    return numerator / denominator.mask(denominator == 0)


def build_channel_performance() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    ga4 = read_csv(DATA_RAW_DIR / "ga4_channel_90d.csv")
    if not ga4.empty:
        ga4 = numeric(ga4, ["sessions", "engagedSessions", "conversions", "ecommercePurchases", "totalRevenue"])
        grouped = ga4.groupby("sessionDefaultChannelGroup", dropna=False).agg(
            sessions=("sessions", "sum"),
            engaged_sessions=("engagedSessions", "sum"),
            conversions=("conversions", "sum"),
            orders=("ecommercePurchases", "sum"),
            revenue=("totalRevenue", "sum"),
        ).reset_index()
        grouped["source"] = "GA4"
        grouped["channel"] = grouped["sessionDefaultChannelGroup"].fillna("(not set)")
        grouped["clicks"] = 0
        grouped["cost"] = 0.0
        frames.append(grouped[["source", "channel", "sessions", "engaged_sessions", "clicks", "cost", "conversions", "orders", "revenue"]])

    shopify_by_order = read_csv(DATA_RAW_DIR / "shopify_sales_by_order_90d.csv")
    shopify = read_csv(DATA_RAW_DIR / "shopify_orders_90d.csv")
    if not shopify_by_order.empty:
        shopify_by_order = numeric(shopify_by_order, ["orders", "total_sales"])
        frames.append(
            pd.DataFrame(
                [
                    {
                        "source": "Shopify",
                        "channel": "Store Orders",
                        "sessions": 0,
                        "engaged_sessions": 0,
                        "clicks": 0,
                        "cost": 0.0,
                        "conversions": shopify_by_order["orders"].sum(),
                        "orders": shopify_by_order["orders"].sum(),
                        "revenue": shopify_by_order["total_sales"].sum(),
                    }
                ]
            )
        )
    elif not shopify.empty:
        shopify = numeric(shopify, ["total_price"])
        frames.append(
            pd.DataFrame(
                [
                    {
                        "source": "Shopify",
                        "channel": "Store Orders",
                        "sessions": 0,
                        "engaged_sessions": 0,
                        "clicks": 0,
                        "cost": 0.0,
                        "conversions": len(shopify),
                        "orders": len(shopify),
                        "revenue": shopify["total_price"].sum(),
                    }
                ]
            )
        )

    ads = read_csv(DATA_RAW_DIR / "google_ads_ad_group_90d.csv")
    if not ads.empty:
        ads = numeric(ads, ["impressions", "clicks", "cost", "conversions", "conversion_value"])
        frames.append(
            pd.DataFrame(
                [
                    {
                        "source": "Google Ads",
                        "channel": "Paid Search",
                        "sessions": 0,
                        "engaged_sessions": 0,
                        "clicks": ads["clicks"].sum(),
                        "cost": ads["cost"].sum(),
                        "conversions": ads["conversions"].sum(),
                        "orders": ads["conversions"].sum(),
                        "revenue": ads["conversion_value"].sum(),
                    }
                ]
            )
        )

    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["source", "channel", "sessions", "engaged_sessions", "clicks", "cost", "conversions", "orders", "revenue"]
    )
    output = numeric(output, ["sessions", "engaged_sessions", "clicks", "cost", "conversions", "orders", "revenue"])
    output["conversion_rate"] = safe_divide(output["orders"], output["sessions"].where(output["sessions"] > 0, output["clicks"])).fillna(0)
    output["roas"] = safe_divide(output["revenue"], output["cost"]).fillna(0)
    output["cpa"] = safe_divide(output["cost"], output["conversions"]).fillna(0)
    return output.sort_values(["revenue", "sessions", "clicks"], ascending=False)


def build_landing_page_performance() -> pd.DataFrame:
    ga4 = read_csv(DATA_RAW_DIR / "ga4_landing_pages_90d.csv")
    events = read_csv(DATA_RAW_DIR / "ga4_landing_page_events_90d.csv")
    ads_lp = read_csv(DATA_RAW_DIR / "google_ads_landing_pages_90d.csv")

    if ga4.empty and ads_lp.empty:
        return pd.DataFrame(
            columns=[
                "landing_page_url",
                "sessions",
                "engaged_sessions",
                "add_to_cart",
                "orders",
                "revenue",
                "ad_clicks",
                "ad_cost",
                "conversion_rate",
                "add_to_cart_rate",
                "diagnosis",
            ]
        )

    if not ga4.empty:
        ga4 = numeric(ga4, ["sessions", "engagedSessions", "conversions", "ecommercePurchases", "totalRevenue"])
        ga4["landing_page_url"] = ga4["landing_page_url"].fillna("").map(normalize_url)
        landing = ga4.groupby("landing_page_url", dropna=False).agg(
            sessions=("sessions", "sum"),
            engaged_sessions=("engagedSessions", "sum"),
            conversions=("conversions", "sum"),
            orders=("ecommercePurchases", "sum"),
            revenue=("totalRevenue", "sum"),
        ).reset_index()
    else:
        landing = pd.DataFrame(columns=["landing_page_url", "sessions", "engaged_sessions", "conversions", "orders", "revenue"])

    if not events.empty:
        events = numeric(events, ["eventCount"])
        events["landing_page_url"] = events["landing_page_url"].fillna("").map(normalize_url)
        atc = events.groupby("landing_page_url", dropna=False).agg(add_to_cart=("eventCount", "sum")).reset_index()
        landing = landing.merge(atc, on="landing_page_url", how="left")
    else:
        landing["add_to_cart"] = 0

    if not ads_lp.empty:
        ads_lp = numeric(ads_lp, ["clicks", "cost", "conversions", "conversion_value"])
        ads_lp["landing_page_url"] = ads_lp["landing_page_url"].fillna("").map(normalize_url)
        ads_landing = ads_lp.groupby("landing_page_url", dropna=False).agg(
            ad_clicks=("clicks", "sum"),
            ad_cost=("cost", "sum"),
            ad_conversions=("conversions", "sum"),
            ad_conversion_value=("conversion_value", "sum"),
        ).reset_index()
        landing = landing.merge(ads_landing, on="landing_page_url", how="outer")
    else:
        landing["ad_clicks"] = 0
        landing["ad_cost"] = 0.0
        landing["ad_conversions"] = 0
        landing["ad_conversion_value"] = 0.0

    landing = numeric(
        landing.fillna(0),
        ["sessions", "engaged_sessions", "conversions", "orders", "revenue", "add_to_cart", "ad_clicks", "ad_cost", "ad_conversions", "ad_conversion_value"],
    )
    traffic_base = landing["ad_clicks"].where(landing["ad_clicks"] > 0, landing["sessions"])
    landing["conversion_rate"] = safe_divide(landing["orders"], landing["sessions"]).fillna(0)
    landing["add_to_cart_rate"] = safe_divide(landing["add_to_cart"], traffic_base).fillna(0)
    landing["diagnosis"] = ""
    high_traffic_low_atc = (traffic_base >= 100) & (landing["add_to_cart_rate"] < 0.02)
    landing.loc[high_traffic_low_atc, "diagnosis"] = "high_click_low_add_to_cart"
    return landing.sort_values(["ad_clicks", "sessions", "revenue"], ascending=False)


def build_google_ads_diagnosis() -> pd.DataFrame:
    ads = read_csv(DATA_RAW_DIR / "google_ads_ad_group_90d.csv")
    if ads.empty:
        return pd.DataFrame(
            columns=["campaign_id", "campaign_name", "ad_group_id", "ad_group_name", "impressions", "clicks", "cost", "conversions", "conversion_value", "ctr", "cvr", "roas", "cpa", "diagnosis"]
        )

    ads = numeric(ads, ["impressions", "clicks", "cost", "conversions", "conversion_value"])
    output = ads.groupby(["campaign_id", "campaign_name", "ad_group_id", "ad_group_name"], dropna=False).agg(
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        cost=("cost", "sum"),
        conversions=("conversions", "sum"),
        conversion_value=("conversion_value", "sum"),
    ).reset_index()
    output["ctr"] = safe_divide(output["clicks"], output["impressions"]).fillna(0)
    output["cvr"] = safe_divide(output["conversions"], output["clicks"]).fillna(0)
    output["roas"] = safe_divide(output["conversion_value"], output["cost"]).fillna(0)
    output["cpa"] = safe_divide(output["cost"], output["conversions"]).fillna(0)
    median_cost = output["cost"].median() if len(output) else 0
    high_cost = output["cost"] >= max(50, median_cost)
    low_conversion = output["conversions"] < 1
    low_roas = output["roas"] < 1
    output["diagnosis"] = ""
    output.loc[high_cost & low_conversion, "diagnosis"] = "high_spend_low_conversion"
    output.loc[high_cost & ~low_conversion & low_roas, "diagnosis"] = "high_spend_low_roas"
    return output.sort_values(["cost", "clicks"], ascending=False)


def build_search_query_opportunities() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    gsc = read_csv(DATA_RAW_DIR / "gsc_90d.csv")
    ads_terms = read_csv(DATA_RAW_DIR / "google_ads_search_terms_90d.csv")

    paid_terms = set()
    if not ads_terms.empty and "search_term" in ads_terms.columns:
        paid_terms = set(ads_terms["search_term"].dropna().astype(str).str.lower().str.strip())

    if not gsc.empty:
        gsc = numeric(gsc, ["clicks", "impressions", "ctr", "position"])
        organic = gsc.groupby(["query", "page"], dropna=False).agg(
            clicks=("clicks", "sum"),
            impressions=("impressions", "sum"),
            ctr=("ctr", "mean"),
            position=("position", "mean"),
        ).reset_index()
        organic["keyword"] = organic["query"].astype(str).str.lower().str.strip()
        organic["source"] = "GSC"
        organic.loc[(organic["impressions"] >= 500) & (organic["ctr"] < 0.02), "opportunity_type"] = "high_impression_low_ctr"
        organic["paid_coverage"] = organic["keyword"].isin(paid_terms)
        organic["cost"] = 0.0
        organic["conversions"] = 0.0
        organic["conversion_value"] = 0.0
        organic_base = organic[["source", "keyword", "query", "page", "clicks", "impressions", "ctr", "position", "paid_coverage", "cost", "conversions", "conversion_value"]]
        organic_opportunities = [
            ("high_impression_low_ctr", (organic["impressions"] >= 500) & (organic["ctr"] < 0.02)),
            ("rank_4_20", organic["position"].between(4, 20)),
            ("seo_keyword_for_ads", organic["position"].between(4, 20) & (~organic["keyword"].isin(paid_terms))),
        ]
        for opportunity_type, mask in organic_opportunities:
            subset = organic_base[mask].copy()
            if subset.empty:
                continue
            subset["opportunity_type"] = opportunity_type
            rows.append(subset[["source", "opportunity_type", "keyword", "query", "page", "clicks", "impressions", "ctr", "position", "paid_coverage", "cost", "conversions", "conversion_value"]])

    if not ads_terms.empty:
        ads_terms = numeric(ads_terms, ["clicks", "impressions", "cost", "conversions", "conversion_value"])
        paid = ads_terms.groupby("search_term", dropna=False).agg(
            clicks=("clicks", "sum"),
            impressions=("impressions", "sum"),
            cost=("cost", "sum"),
            conversions=("conversions", "sum"),
            conversion_value=("conversion_value", "sum"),
        ).reset_index()
        paid["keyword"] = paid["search_term"].astype(str).str.lower().str.strip()
        paid["source"] = "Google Ads"
        paid["query"] = paid["search_term"]
        paid["page"] = ""
        paid["ctr"] = safe_divide(paid["clicks"], paid["impressions"]).fillna(0)
        paid["position"] = 0.0
        paid["paid_coverage"] = True
        paid["roas"] = safe_divide(paid["conversion_value"], paid["cost"]).fillna(0)
        paid["opportunity_type"] = ""
        paid.loc[(paid["conversions"] >= 1) | (paid["roas"] >= 2), "opportunity_type"] = "ads_keyword_for_seo"
        rows.append(paid[["source", "opportunity_type", "keyword", "query", "page", "clicks", "impressions", "ctr", "position", "paid_coverage", "cost", "conversions", "conversion_value"]])

    output = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["source", "opportunity_type", "keyword", "query", "page", "clicks", "impressions", "ctr", "position", "paid_coverage", "cost", "conversions", "conversion_value"]
    )
    output = output[output["opportunity_type"].fillna("") != ""]
    return output.sort_values(["opportunity_type", "impressions", "clicks"], ascending=[True, False, False])


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform raw GA4, Shopify, GSC, and Google Ads exports into diagnosis-ready CSV files.")
    parser.parse_args()

    ensure_dirs()
    outputs = {
        "channel_performance.csv": build_channel_performance(),
        "landing_page_performance.csv": build_landing_page_performance(),
        "google_ads_diagnosis.csv": build_google_ads_diagnosis(),
        "search_query_opportunities.csv": build_search_query_opportunities(),
    }
    for filename, frame in outputs.items():
        path = DATA_PROCESSED_DIR / filename
        frame.to_csv(path, index=False)
        LOGGER.info("Processed rows=%s out=%s", len(frame), path)


if __name__ == "__main__":
    main()
