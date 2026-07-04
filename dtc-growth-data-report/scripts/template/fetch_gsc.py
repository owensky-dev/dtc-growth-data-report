from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import DATA_RAW_DIR, default_date_range, ensure_dirs, load_settings, setup_logging


LOGGER = setup_logging("fetch_gsc")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
COLUMNS = [
    "date",
    "page",
    "query",
    "country",
    "device",
    "clicks",
    "impressions",
    "ctr",
    "position",
]


def fetch_gsc_rows(
    key_file: str,
    site_url: str,
    start_date: str,
    end_date: str,
    row_limit: int = 25000,
) -> list[dict]:
    credentials = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)

    rows: list[dict] = []
    start_row = 0
    dimensions = ["date", "page", "query", "country", "device"]

    while True:
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "startRow": start_row,
        }
        LOGGER.info("Fetching GSC rows startRow=%s", start_row)
        response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        batch = response.get("rows", [])
        if not batch:
            break

        for item in batch:
            keys = item.get("keys", [])
            record = {
                dimension: keys[index] if index < len(keys) else ""
                for index, dimension in enumerate(dimensions)
            }
            record.update(
                {
                    "clicks": item.get("clicks", 0),
                    "impressions": item.get("impressions", 0),
                    "ctr": item.get("ctr", 0),
                    "position": item.get("position", 0),
                }
            )
            rows.append(record)

        if len(batch) < row_limit:
            break
        start_row += row_limit

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Google Search Console search performance data.")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--out", default=str(DATA_RAW_DIR / "gsc_90d.csv"))
    args = parser.parse_args()

    ensure_dirs()
    settings = load_settings(["GOOGLE_APPLICATION_CREDENTIALS", "GSC_SITE_URL"])
    start_date, end_date = (
        (args.start_date, args.end_date)
        if args.start_date and args.end_date
        else default_date_range(args.days)
    )

    rows = fetch_gsc_rows(
        key_file=settings["GOOGLE_APPLICATION_CREDENTIALS"],
        site_url=settings["GSC_SITE_URL"],
        start_date=start_date,
        end_date=end_date,
    )
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLUMNS).to_csv(output_path, index=False)
    LOGGER.info("GSC rows=%s date_range=%s..%s out=%s", len(rows), start_date, end_date, output_path)


if __name__ == "__main__":
    main()
