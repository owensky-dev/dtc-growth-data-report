# Data Contract

## Raw Files

The standard pipeline writes raw source files to `data/raw/`.

### GA4

- `ga4_channel_90d.csv`: `date`, `sessionDefaultChannelGroup`, `sessions`, `engagedSessions`, `conversions`, `ecommercePurchases`, `totalRevenue`
- `ga4_landing_pages_90d.csv`: `landingPagePlusQueryString`, `landing_page_url`, `sessions`, `engagedSessions`, `conversions`, `ecommercePurchases`, `totalRevenue`
- `ga4_landing_page_events_90d.csv`: `date`, `landingPagePlusQueryString`, `landing_page_url`, `eventName`, `eventCount`. The standard fetch includes both `add_to_cart` and `begin_checkout` so weekly funnel stages can be compared by date.

### GSC

- `gsc_daily_90d.csv`: site-level `date`, `clicks`, `impressions`, `ctr`, `position`, fetched with `dimensions=["date"]` and `aggregationType="byProperty"`. This is authoritative for weekly GSC KPIs and date coverage.
- `gsc_90d.csv`: `date`, `page`, `query`, `country`, `device`, `clicks`, `impressions`, `ctr`, `position`. Use it only for query/page SEO detail; do not sum it into sitewide KPIs because anonymous queries are omitted and page aggregation changes totals.

### Google Ads

- `google_ads_campaign_90d.csv`: required daily campaign facts with `date`, `campaign_id`, `campaign_name`, `campaign_status`, `campaign_type`, `impressions`, `clicks`, `cost`, `conversions`, `conversion_value`, `all_conversions`, `all_conversion_value`. Weekly totals and campaign reporting use this file so Performance Max is included.
- `google_ads_ad_group_90d.csv`: `date`, `campaign_id`, `campaign_name`, `ad_group_id`, `ad_group_name`, `impressions`, `clicks`, `cost`, `conversions`, `conversion_value`
- `google_ads_search_terms_90d.csv`: ad group fields plus `search_term`
- `google_ads_landing_pages_90d.csv`: ad group fields plus `landing_page_url`

`cost` must be converted from micros into normal currency units.

### Shopify

- `shopify_orders_90d.csv`: `created_at`, `date`, `order_id`, `order_name`, `currency`, `subtotal_price`, `total_price`, `total_tax`, `financial_status`, `fulfillment_status`, `test`, `cancelled_at`, `source_name`, `landing_site`, `referring_site`. `date` is derived by converting `created_at` into `GA4_PROPERTY_TIMEZONE`.
- `shopify_sales_by_day_90d.csv`: `date`, `orders`, `total_sales`. It includes zero-order days and aggregates only paid, non-test, non-cancelled orders. This file is required for weekly reports because it distinguishes "no orders" from "Shopify data was not fetched."
- For each weekly comparison window, the paid/non-test/non-cancelled count and `total_price` sum from `shopify_orders_90d.csv` must reconcile to `orders` and `total_sales` in `shopify_sales_by_day_90d.csv` (revenue tolerance `0.01`). A mismatch indicates partial or stale Shopify raw data and must stop report generation.
- Optional connector materialization: `shopify_sales_by_order_90d.csv`, `shopify_sales_by_product_90d.csv`

## Weekly Coverage Contract

Weekly reports must be generated only for a date window covered by all four core sources:

- GA4: at least one row for each report date in `ga4_channel_90d.csv`.
- Shopify: one row for each report date in `shopify_sales_by_day_90d.csv`, including days with `orders = 0`.
- Google Ads: at least one row for each report date in `google_ads_campaign_90d.csv`.
- GSC: one property-level row for each report date in `gsc_daily_90d.csv`.

The default report window is the latest 7-day period satisfying this rule. The previous 7 days must also satisfy the same coverage rule for week-over-week comparison. If no such 14-day comparison window exists, the generator must fail with source/date gaps instead of producing a partial report.

## Processed Files

The transform step should produce:

- `data/processed/channel_performance.csv`
- `data/processed/landing_page_performance.csv`
- `data/processed/google_ads_diagnosis.csv`
- `data/processed/search_query_opportunities.csv`

## Metric Defaults

- Revenue and orders: Shopify.
- Sessions and landing behavior: GA4.
- Ad spend, ad clicks, ad conversions, ad conversion value: Google Ads campaign-level daily facts, including Performance Max.
- SEO impressions, clicks, CTR, average position: GSC property-level daily totals from `gsc_daily_90d.csv`.
- Store conversion rate: Shopify orders divided by GA4 sessions.
- Sitewide ROI: Shopify revenue divided by total Google Ads cost for the same aligned period.
- Purchase tracking rate: GA4 `ecommercePurchases` divided by Shopify Online Store paid, non-test, non-cancelled orders (`source_name=web`) for the same aligned period. When both are zero, report 100% coverage rather than a divide-by-zero error.
- Purchase count gap: Shopify Online Store orders minus GA4 `ecommercePurchases`. Purchase revenue gap: Shopify Online Store revenue minus GA4 `totalRevenue`. Persist Shop/POS/draft/app/offsite counts and revenue separately; they remain in Shopify business KPIs but are not treated as browser tracking failures. These aggregate fields are health signals only; exact missing orders require Shopify paid-order IDs versus BigQuery `transaction_id` reconciliation.
- Add-to-cart rate: GA4 `add_to_cart` events divided by GA4 sessions for the same report period.
- Cart-to-checkout rate: GA4 `begin_checkout` events divided by GA4 `add_to_cart` events for the same report period.
- ROAS: Google Ads conversion value divided by Google Ads cost.
- CPA: Google Ads cost divided by Google Ads conversions; show `n/a` when conversions are zero.

The weekly JSON must persist `site_roi` for current and previous periods. The core KPI table must include GSC clicks, impressions, and CTR.
