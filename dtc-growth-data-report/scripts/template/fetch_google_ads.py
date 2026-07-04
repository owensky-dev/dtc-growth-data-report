from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config import DATA_RAW_DIR, default_date_range, ensure_dirs, load_settings, setup_logging


LOGGER = setup_logging("fetch_google_ads")
PERFORMANCE_COLUMNS = [
    "date",
    "campaign_id",
    "campaign_name",
    "ad_group_id",
    "ad_group_name",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "conversion_value",
]
SEARCH_TERM_COLUMNS = [
    "date",
    "campaign_id",
    "campaign_name",
    "ad_group_id",
    "ad_group_name",
    "search_term",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "conversion_value",
]
LANDING_PAGE_COLUMNS = [
    "date",
    "campaign_id",
    "campaign_name",
    "ad_group_id",
    "ad_group_name",
    "landing_page_url",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "conversion_value",
]


def load_google_ads_client(config_file: str | None = None):
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError as exc:
        raise RuntimeError(
            "Missing google-ads package. Install dependencies from requirements.txt before fetching Google Ads."
        ) from exc

    if config_file:
        return GoogleAdsClient.load_from_storage(config_file)

    settings = load_settings()
    if settings.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH"):
        return GoogleAdsClient.load_from_storage(settings["GOOGLE_ADS_CONFIGURATION_FILE_PATH"])

    oauth_fields = {
        "developer_token": settings.get("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": settings.get("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": settings.get("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": settings.get("GOOGLE_ADS_REFRESH_TOKEN"),
        "login_customer_id": settings.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or settings.get("GOOGLE_ADS_CUSTOMER_ID"),
        "use_proto_plus": settings.get("GOOGLE_ADS_USE_PROTO_PLUS", "True").lower() == "true",
    }
    missing = [key for key, value in oauth_fields.items() if key != "use_proto_plus" and not value]
    if missing:
        raise RuntimeError(
            "Google Ads API configuration is incomplete. Fill GOOGLE_ADS_CONFIGURATION_FILE_PATH "
            f"or these .env values: {', '.join(missing)}."
        )
    return GoogleAdsClient.load_from_dict(oauth_fields)


def clean_customer_id(customer_id: str) -> str:
    return customer_id.replace("-", "").strip()


def stream_query(client, customer_id: str, query: str):
    service = client.get_service("GoogleAdsService")
    return service.search_stream(customer_id=clean_customer_id(customer_id), query=query)


def fetch_ad_group_performance(client, customer_id: str, start_date: str, end_date: str) -> list[dict]:
    query = f"""
        SELECT
          segments.date,
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM ad_group
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY segments.date, campaign.id, ad_group.id
    """
    rows: list[dict] = []
    LOGGER.info("Fetching Google Ads ad group performance")
    for batch in stream_query(client, customer_id, query):
        for item in batch.results:
            rows.append(
                {
                    "date": item.segments.date,
                    "campaign_id": item.campaign.id,
                    "campaign_name": item.campaign.name,
                    "ad_group_id": item.ad_group.id,
                    "ad_group_name": item.ad_group.name,
                    "impressions": item.metrics.impressions,
                    "clicks": item.metrics.clicks,
                    "cost": item.metrics.cost_micros / 1_000_000,
                    "conversions": float(item.metrics.conversions),
                    "conversion_value": float(item.metrics.conversions_value),
                }
            )
    return rows


def fetch_search_terms(client, customer_id: str, start_date: str, end_date: str) -> list[dict]:
    query = f"""
        SELECT
          segments.date,
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          search_term_view.search_term,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.clicks DESC
    """
    rows: list[dict] = []
    LOGGER.info("Fetching Google Ads search terms")
    for batch in stream_query(client, customer_id, query):
        for item in batch.results:
            rows.append(
                {
                    "date": item.segments.date,
                    "campaign_id": item.campaign.id,
                    "campaign_name": item.campaign.name,
                    "ad_group_id": item.ad_group.id,
                    "ad_group_name": item.ad_group.name,
                    "search_term": item.search_term_view.search_term,
                    "impressions": item.metrics.impressions,
                    "clicks": item.metrics.clicks,
                    "cost": item.metrics.cost_micros / 1_000_000,
                    "conversions": float(item.metrics.conversions),
                    "conversion_value": float(item.metrics.conversions_value),
                }
            )
    return rows


def fetch_landing_pages(client, customer_id: str, start_date: str, end_date: str) -> list[dict]:
    query = f"""
        SELECT
          segments.date,
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          expanded_landing_page_view.expanded_final_url,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM expanded_landing_page_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.clicks DESC
    """
    rows: list[dict] = []
    LOGGER.info("Fetching Google Ads landing pages")
    for batch in stream_query(client, customer_id, query):
        for item in batch.results:
            rows.append(
                {
                    "date": item.segments.date,
                    "campaign_id": item.campaign.id,
                    "campaign_name": item.campaign.name,
                    "ad_group_id": item.ad_group.id,
                    "ad_group_name": item.ad_group.name,
                    "landing_page_url": item.expanded_landing_page_view.expanded_final_url,
                    "impressions": item.metrics.impressions,
                    "clicks": item.metrics.clicks,
                    "cost": item.metrics.cost_micros / 1_000_000,
                    "conversions": float(item.metrics.conversions),
                    "conversion_value": float(item.metrics.conversions_value),
                }
            )
    return rows


def write_frame(rows: list[dict], columns: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    LOGGER.info("Wrote rows=%s out=%s", len(rows), path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Google Ads data for the latest 90-day growth diagnosis window.")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--customer-id", help="Google Ads customer ID. Defaults to GOOGLE_ADS_CUSTOMER_ID.")
    parser.add_argument("--config-file", help="Optional google-ads.yaml path.")
    args = parser.parse_args()

    ensure_dirs()
    settings = load_settings(["GOOGLE_ADS_CUSTOMER_ID"] if not args.customer_id else [])
    customer_id = args.customer_id or settings["GOOGLE_ADS_CUSTOMER_ID"]
    start_date, end_date = (
        (args.start_date, args.end_date)
        if args.start_date and args.end_date
        else default_date_range(args.days)
    )

    client = load_google_ads_client(args.config_file)
    performance_rows = fetch_ad_group_performance(client, customer_id, start_date, end_date)
    write_frame(performance_rows, PERFORMANCE_COLUMNS, DATA_RAW_DIR / "google_ads_ad_group_90d.csv")

    optional_fetches = [
        (fetch_search_terms, SEARCH_TERM_COLUMNS, DATA_RAW_DIR / "google_ads_search_terms_90d.csv"),
        (fetch_landing_pages, LANDING_PAGE_COLUMNS, DATA_RAW_DIR / "google_ads_landing_pages_90d.csv"),
    ]
    for fetcher, columns, path in optional_fetches:
        try:
            rows = fetcher(client, customer_id, start_date, end_date)
        except Exception as exc:
            LOGGER.warning("Optional Google Ads fetch failed for %s: %s", path.name, exc)
            rows = []
        write_frame(rows, columns, path)

    LOGGER.info("Google Ads date_range=%s..%s complete", start_date, end_date)


if __name__ == "__main__":
    main()
