# Configuration Reference

Use `.env` or local environment variables. Never hard-code credentials in scripts or reports.

## Required For GA4

- `GOOGLE_APPLICATION_CREDENTIALS`: absolute path to a Google service account JSON file.
- `GA4_PROPERTY_ID`: GA4 property ID.

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
- `SHOPIFY_ADMIN_ACCESS_TOKEN`
- `SHOPIFY_API_VERSION`: default to a current supported Admin API version.

If a connector is used instead of an Admin token, materialize order-level data into `data/raw/shopify_orders_90d.csv` or `data/raw/shopify_sales_by_order_90d.csv` before transforming.

## Optional

- `SITE_BASE_URL`: used to normalize GA4/GSC/Google Ads landing page URLs.
- `LOG_LEVEL`: default `INFO`.

## Safety

Do not copy `.env` into shared skills, repos, report bundles, screenshots, or final replies. Only share `.env.example`.
