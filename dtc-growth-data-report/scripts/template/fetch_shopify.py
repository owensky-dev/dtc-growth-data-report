from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config import DATA_RAW_DIR, default_date_range, ensure_dirs, load_settings, setup_logging


LOGGER = setup_logging("fetch_shopify")
COLUMNS = [
    "created_at",
    "date",
    "order_id",
    "order_name",
    "currency",
    "subtotal_price",
    "total_price",
    "original_total_price",
    "total_refunded",
    "total_tax",
    "financial_status",
    "fulfillment_status",
    "test",
    "cancelled_at",
    "source_name",
    "landing_site",
    "referring_site",
]

DAILY_COLUMNS = ["date", "orders", "total_sales"]


ORDERS_QUERY = """
query Orders($first: Int!, $after: String, $query: String!) {
  orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        test
        cancelledAt
        sourceName
        landingPageUrl
        referrerUrl
        currentSubtotalPriceSet { shopMoney { amount currencyCode } }
        currentTotalPriceSet { shopMoney { amount currencyCode } }
        originalTotalPriceSet { shopMoney { amount currencyCode } }
        totalRefundedSet { shopMoney { amount currencyCode } }
        currentTotalTaxSet { shopMoney { amount currencyCode } }
      }
    }
  }
}
"""


def shopify_endpoint(shop_domain: str, api_version: str) -> str:
    domain = shop_domain.replace("https://", "").replace("http://", "").strip("/")
    return f"https://{domain}/admin/api/{api_version}/graphql.json"


def shopify_token_endpoint(shop_domain: str) -> str:
    domain = shop_domain.replace("https://", "").replace("http://", "").strip("/")
    return f"https://{domain}/admin/oauth/access_token"


def client_credentials_token(shop_domain: str, client_id: str, client_secret: str) -> str:
    response = requests.post(
        shopify_token_endpoint(shop_domain),
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Accept": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    token = response.json().get("access_token", "")
    if not token:
        raise RuntimeError("Shopify token exchange returned no access token")
    return token


def money_amount(node: dict, field: str) -> float:
    try:
        return float(node.get(field, {}).get("shopMoney", {}).get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def local_order_date(created_at: str, report_timezone: str) -> str:
    parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo(report_timezone)).date().isoformat()


def fetch_orders(
    shop_domain: str,
    access_token: str,
    api_version: str,
    start_date: str,
    end_date: str,
    report_timezone: str,
) -> list[dict]:
    endpoint = shopify_endpoint(shop_domain, api_version)
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    query_start = (date.fromisoformat(start_date) - timedelta(days=2)).isoformat()
    query_end = (date.fromisoformat(end_date) + timedelta(days=2)).isoformat()
    query = f"created_at:>={query_start} created_at:<={query_end}"
    variables = {"first": 100, "after": None, "query": query}
    rows: list[dict] = []

    while True:
        LOGGER.info("Fetching Shopify orders after=%s", variables["after"] or "START")
        response = requests.post(
            endpoint,
            headers=headers,
            json={"query": ORDERS_QUERY, "variables": variables},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"Shopify GraphQL error: {payload['errors']}")

        orders = payload.get("data", {}).get("orders", {})
        for edge in orders.get("edges", []):
            node = edge.get("node", {})
            created_at = node.get("createdAt", "")
            date_value = local_order_date(created_at, report_timezone)
            if not start_date <= date_value <= end_date:
                continue
            currency = (
                node.get("currentTotalPriceSet", {})
                .get("shopMoney", {})
                .get("currencyCode", "")
            )
            rows.append(
                {
                    "created_at": created_at,
                    "date": date_value,
                    "order_id": node.get("id", ""),
                    "order_name": node.get("name", ""),
                    "currency": currency,
                    "subtotal_price": money_amount(node, "currentSubtotalPriceSet"),
                    "total_price": money_amount(node, "currentTotalPriceSet"),
                    "original_total_price": money_amount(node, "originalTotalPriceSet"),
                    "total_refunded": money_amount(node, "totalRefundedSet"),
                    "total_tax": money_amount(node, "currentTotalTaxSet"),
                    "financial_status": node.get("displayFinancialStatus", ""),
                    "fulfillment_status": node.get("displayFulfillmentStatus", ""),
                    "test": bool(node.get("test", False)),
                    "cancelled_at": node.get("cancelledAt", "") or "",
                    "source_name": node.get("sourceName", ""),
                    "landing_site": node.get("landingPageUrl", ""),
                    "referring_site": node.get("referrerUrl", ""),
                }
            )

        page_info = orders.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        variables["after"] = page_info.get("endCursor")

    return rows


def build_daily_sales(rows: list[dict], start_date: str, end_date: str) -> pd.DataFrame:
    daily = pd.DataFrame({"date": pd.date_range(start_date, end_date, freq="D").strftime("%Y-%m-%d")})
    if not rows:
        daily["orders"] = 0
        daily["total_sales"] = 0.0
        return daily[DAILY_COLUMNS]

    orders = pd.DataFrame(rows)
    paid = orders["financial_status"].fillna("").astype(str).str.upper().eq("PAID")
    non_test = pd.Series(True, index=orders.index)
    not_cancelled = pd.Series(True, index=orders.index)
    if "test" in orders.columns:
        non_test &= ~orders["test"].fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})
    if "cancelled_at" in orders.columns:
        not_cancelled &= orders["cancelled_at"].fillna("").astype(str).str.strip().eq("")
    orders = orders[paid & non_test & not_cancelled].copy()
    orders["date"] = pd.to_datetime(orders["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    orders["total_price"] = pd.to_numeric(orders["total_price"], errors="coerce").fillna(0)
    grouped = orders.groupby("date", dropna=False).agg(
        orders=("order_name", "count"),
        total_sales=("total_price", "sum"),
    ).reset_index()
    daily = daily.merge(grouped, on="date", how="left")
    daily["orders"] = pd.to_numeric(daily["orders"], errors="coerce").fillna(0).astype(int)
    daily["total_sales"] = pd.to_numeric(daily["total_sales"], errors="coerce").fillna(0.0)
    return daily[DAILY_COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Shopify orders for the latest growth diagnosis window.")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--out", default=str(DATA_RAW_DIR / "shopify_orders_90d.csv"))
    parser.add_argument("--daily-out", default=str(DATA_RAW_DIR / "shopify_sales_by_day_90d.csv"))
    parser.add_argument("--timezone")
    args = parser.parse_args()

    ensure_dirs()
    settings = load_settings(["SHOPIFY_SHOP_DOMAIN"])
    api_version = settings.get("SHOPIFY_API_VERSION", "2026-01")
    report_timezone = args.timezone or settings.get("GA4_PROPERTY_TIMEZONE", "")
    if not report_timezone:
        raise RuntimeError(
            "Missing GA4_PROPERTY_TIMEZONE. Set the GA4 Property IANA timezone "
            "so Shopify orders align to the report date window."
        )
    ZoneInfo(report_timezone)
    start_date, end_date = (
        (args.start_date, args.end_date)
        if args.start_date and args.end_date
        else default_date_range(args.days)
    )

    if settings.get("SHOPIFY_CLIENT_ID") and settings.get("SHOPIFY_CLIENT_SECRET"):
        access_token = client_credentials_token(
            settings["SHOPIFY_SHOP_DOMAIN"],
            settings["SHOPIFY_CLIENT_ID"],
            settings["SHOPIFY_CLIENT_SECRET"],
        )
    elif settings.get("SHOPIFY_ADMIN_ACCESS_TOKEN"):
        access_token = settings["SHOPIFY_ADMIN_ACCESS_TOKEN"]
    else:
        raise RuntimeError(
            "Missing Shopify authentication: set SHOPIFY_ADMIN_ACCESS_TOKEN or both "
            "SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET."
        )

    rows = fetch_orders(
        shop_domain=settings["SHOPIFY_SHOP_DOMAIN"],
        access_token=access_token,
        api_version=api_version,
        start_date=start_date,
        end_date=end_date,
        report_timezone=report_timezone,
    )
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLUMNS).to_csv(output_path, index=False)
    daily_path = Path(args.daily_out)
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_sales = build_daily_sales(rows, start_date, end_date)
    daily_sales.to_csv(daily_path, index=False)
    LOGGER.info(
        "Shopify rows=%s date_range=%s..%s timezone=%s out=%s",
        len(rows),
        start_date,
        end_date,
        report_timezone,
        output_path,
    )
    LOGGER.info("Shopify daily rows=%s out=%s", len(daily_sales), daily_path)


if __name__ == "__main__":
    main()
