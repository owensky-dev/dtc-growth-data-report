from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest
from google.oauth2 import service_account

from config import DATA_RAW_DIR, default_date_range, ensure_dirs, load_settings, normalize_url, setup_logging


LOGGER = setup_logging("fetch_ga4")

CHANNEL_COLUMNS = [
    "date",
    "sessionDefaultChannelGroup",
    "sessions",
    "engagedSessions",
    "conversions",
    "ecommercePurchases",
    "totalRevenue",
]
LANDING_PAGE_COLUMNS = [
    "landingPagePlusQueryString",
    "landing_page_url",
    "sessions",
    "engagedSessions",
    "conversions",
    "ecommercePurchases",
    "totalRevenue",
]
LANDING_PAGE_EVENT_COLUMNS = [
    "landingPagePlusQueryString",
    "landing_page_url",
    "eventName",
    "eventCount",
]


def run_report(
    client: BetaAnalyticsDataClient,
    property_name: str,
    dimensions: list[str],
    metrics: list[str],
    start_date: str,
    end_date: str,
    dimension_filter: FilterExpression | None = None,
    limit: int = 100000,
) -> list[dict]:
    rows: list[dict] = []
    offset = 0

    while True:
        request = RunReportRequest(
            property=property_name,
            dimensions=[Dimension(name=name) for name in dimensions],
            metrics=[Metric(name=name) for name in metrics],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimension_filter=dimension_filter,
            limit=limit,
            offset=offset,
        )
        response = client.run_report(request)
        if not response.rows:
            break

        for row in response.rows:
            record = {
                dimensions[index]: value.value
                for index, value in enumerate(row.dimension_values)
            }
            record.update(
                {
                    metrics[index]: float(value.value or 0)
                    for index, value in enumerate(row.metric_values)
                }
            )
            rows.append(record)

        if len(response.rows) < limit:
            break
        offset += limit

    return rows


def fetch_ga4(
    key_file: str,
    property_id: str,
    site_url: str,
    start_date: str,
    end_date: str,
) -> dict[str, pd.DataFrame]:
    credentials = service_account.Credentials.from_service_account_file(key_file)
    client = BetaAnalyticsDataClient(credentials=credentials)
    property_name = f"properties/{property_id}"

    LOGGER.info("Fetching GA4 channel performance for %s..%s", start_date, end_date)
    channel_rows = run_report(
        client,
        property_name,
        dimensions=["date", "sessionDefaultChannelGroup"],
        metrics=["sessions", "engagedSessions", "conversions", "ecommercePurchases", "totalRevenue"],
        start_date=start_date,
        end_date=end_date,
    )

    LOGGER.info("Fetching GA4 landing page performance")
    landing_rows = run_report(
        client,
        property_name,
        dimensions=["landingPagePlusQueryString"],
        metrics=["sessions", "engagedSessions", "conversions", "ecommercePurchases", "totalRevenue"],
        start_date=start_date,
        end_date=end_date,
    )

    LOGGER.info("Fetching GA4 add_to_cart events by landing page")
    event_filter = FilterExpression(
        filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.EXACT,
                value="add_to_cart",
            ),
        )
    )
    event_rows = run_report(
        client,
        property_name,
        dimensions=["landingPagePlusQueryString", "eventName"],
        metrics=["eventCount"],
        start_date=start_date,
        end_date=end_date,
        dimension_filter=event_filter,
    )

    landing_df = pd.DataFrame(landing_rows, columns=["landingPagePlusQueryString", "sessions", "engagedSessions", "conversions", "ecommercePurchases", "totalRevenue"])
    if not landing_df.empty:
        landing_df["landing_page_url"] = landing_df["landingPagePlusQueryString"].map(lambda value: normalize_url(value, site_url))
        landing_df = landing_df[LANDING_PAGE_COLUMNS]

    event_df = pd.DataFrame(event_rows, columns=["landingPagePlusQueryString", "eventName", "eventCount"])
    if not event_df.empty:
        event_df["landing_page_url"] = event_df["landingPagePlusQueryString"].map(lambda value: normalize_url(value, site_url))
        event_df = event_df[LANDING_PAGE_EVENT_COLUMNS]

    return {
        "channel": pd.DataFrame(channel_rows, columns=CHANNEL_COLUMNS),
        "landing_pages": landing_df if not landing_df.empty else pd.DataFrame(columns=LANDING_PAGE_COLUMNS),
        "landing_page_events": event_df if not event_df.empty else pd.DataFrame(columns=LANDING_PAGE_EVENT_COLUMNS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GA4 channel, landing page, and add-to-cart data.")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()

    ensure_dirs()
    settings = load_settings(["GOOGLE_APPLICATION_CREDENTIALS", "GA4_PROPERTY_ID"])
    start_date, end_date = (
        (args.start_date, args.end_date)
        if args.start_date and args.end_date
        else default_date_range(args.days)
    )

    frames = fetch_ga4(
        key_file=settings["GOOGLE_APPLICATION_CREDENTIALS"],
        property_id=settings["GA4_PROPERTY_ID"],
        site_url=settings.get("SITE_BASE_URL", ""),
        start_date=start_date,
        end_date=end_date,
    )
    outputs = {
        "channel": DATA_RAW_DIR / "ga4_channel_90d.csv",
        "landing_pages": DATA_RAW_DIR / "ga4_landing_pages_90d.csv",
        "landing_page_events": DATA_RAW_DIR / "ga4_landing_page_events_90d.csv",
    }
    for name, frame in frames.items():
        path = outputs[name]
        frame.to_csv(path, index=False)
        LOGGER.info("GA4 %s rows=%s out=%s", name, len(frame), path)


if __name__ == "__main__":
    main()
