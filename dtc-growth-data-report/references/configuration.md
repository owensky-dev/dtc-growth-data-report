# Configuration Reference

Use `.env` or local environment variables. Never hard-code credentials in scripts or reports.

## Required For GA4

- `GOOGLE_APPLICATION_CREDENTIALS`: absolute path to a Google service account JSON file.
- `GA4_PROPERTY_ID`: GA4 property ID.
- `GA4_PROPERTY_TIMEZONE`: exact IANA timezone configured on the GA4 Property, such as `America/Los_Angeles`. Shopify `createdAt` timestamps are converted into this timezone before weekly date assignment.

The service account must have access to the GA4 property.

## Required For GSC

- `GOOGLE_APPLICATION_CREDENTIALS`: same service account path can be reused.
- `GSC_SITE_URL`: exact Search Console property URL, such as `https://example.com/` or a domain property string if supported by the script.

The service account must be added to Search Console with access to the property.

## Required For Google Ads

- `GOOGLE_ADS_CUSTOMER_ID`: target account customer ID, digits only or hyphenated; scripts normalize it.
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID`: manager account ID when using an MCC; otherwise usually same as customer ID.

Alternative:

- `GOOGLE_ADS_CONFIGURATION_FILE_PATH`: path to a valid `google-ads.yaml`.

## Required For Shopify

- `SHOPIFY_SHOP_DOMAIN`: store domain, e.g. `brand.myshopify.com`.
- Authentication option A: `SHOPIFY_ADMIN_ACCESS_TOKEN`.
- Authentication option B: `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`; the fetcher exchanges them for a short-lived Admin API token.
- `SHOPIFY_API_VERSION`: default to a current supported Admin API version.

If a connector is used instead of an Admin token, materialize the standard order-level contract into `data/raw/shopify_orders_90d.csv`, including local `date`, payment/test/cancellation status, `source_name`, `order_id`, `total_price`, `original_total_price`, and `total_refunded`. Weekly/monthly purchase integrity requires these rows in addition to `shopify_sales_by_day_90d.csv`.

Exact purchase/refund rates also require GA4 BigQuery Export access through `$ga4-data-analysis`: project ID, GA4 dataset-level Data Viewer, project-level Job User, the same service-account key, and complete `events_YYYYMMDD` tables for the report window. The DTC report remains read-only and only consumes the generated reconciliation JSON.

## Optional

- `SITE_BASE_URL`: used to normalize GA4/GSC/Google Ads landing page URLs.
- `LOG_LEVEL`: default `INFO`.

## Safety

Do not copy `.env` into shared skills, repos, report bundles, screenshots, or final replies. Only share `.env.example`.

If authentication fails, repair or renew it and rerun the source fetch before transforming or generating a weekly report. Do not fall back to stale raw data.
