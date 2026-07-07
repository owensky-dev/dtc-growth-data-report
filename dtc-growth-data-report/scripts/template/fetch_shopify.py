from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

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
    "total_tax",
    "financial_status",
    "fulfillment_status",
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
        sourceName
        landingPageUrl
        referrerUrl
        currentSubtotalPriceSet { shopMoney { amount currencyCode } }
        currentTotalPriceSet { shopMoney { amount currencyCode } }
        currentTotalTaxSet { shopMoney { amount currencyCode } }
      }
    }
  }
}
"""


def shopify_endpoint(shop_domain: str, api_version: str) -> str:
    domain = shop_domain.replace("https://", "").replace("http://", "").strip("/")
    return f"https://{domain}/admin/api/{api_version}/graphql.json"


def money_amount(node: dict, field: str) -> float:
    try:
        return float(node.get(field, {}).get("shopMoney", {}).get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_orders(
    shop_domain: str,
    access_token: str,
    api_version: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    endpoint = shopify_endpoint(shop_domain, api_version)
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    query = f"created_at:>={start_date} created_at:<={end_date}"
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
            date_value = created_at[:10]
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
                    "total_tax": money_amount(node, "currentTotalTaxSet"),
                    "financial_status": node.get("displayFinancialStatus", ""),
                    "fulfillment_status": node.get("displayFulfillmentStatus", ""),
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
    args = parser.parse_args()

    ensure_dirs()
    settings = load_settings(["SHOPIFY_SHOP_DOMAIN", "SHOPIFY_ADMIN_ACCESS_TOKEN"])
    api_version = settings.get("SHOPIFY_API_VERSION", "2026-01")
    start_date, end_date = (
        (args.start_date, args.end_date)
        if args.start_date and args.end_date
        else default_date_range(args.days)
    )

    rows = fetch_orders(
        shop_domain=settings["SHOPIFY_SHOP_DOMAIN"],
        access_token=settings["SHOPIFY_ADMIN_ACCESS_TOKEN"],
        api_version=api_version,
        start_date=start_date,
        end_date=end_date,
    )
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLUMNS).to_csv(output_path, index=False)
    daily_path = Path(args.daily_out)
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_sales = build_daily_sales(rows, start_date, end_date)
    daily_sales.to_csv(daily_path, index=False)
    LOGGER.info("Shopify rows=%s date_range=%s..%s out=%s", len(rows), start_date, end_date, output_path)
    LOGGER.info("Shopify daily rows=%s out=%s", len(daily_sales), daily_path)


if __name__ == "__main__":
    main()
