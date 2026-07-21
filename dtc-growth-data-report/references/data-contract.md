# Data Contract

## Raw Files

The standard pipeline writes raw source files to `data/raw/`.

### GA4

- `ga4_channel_90d.csv`: `date`, `sessionDefaultChannelGroup`, `sessions`, `engagedSessions`, `conversions`, `ecommercePurchases`, `totalRevenue`
- `ga4_landing_pages_90d.csv`: `landingPagePlusQueryString`, `landing_page_url`, `sessions`, `engagedSessions`, `conversions`, `ecommercePurchases`, `totalRevenue`
- `ga4_landing_page_events_90d.csv`: `date`, `landingPagePlusQueryString`, `landing_page_url`, `eventName`, `eventCount`. The standard fetch includes both `add_to_cart` and `begin_checkout` so weekly funnel stages can be compared by date.

### GSC

- `gsc_90d.csv`: `date`, `page`, `query`, `country`, `device`, `clicks`, `impressions`, `ctr`, `position`

### Google Ads

- `google_ads_ad_group_90d.csv`: `date`, `campaign_id`, `campaign_name`, `ad_group_id`, `ad_group_name`, `impressions`, `clicks`, `cost`, `conversions`, `conversion_value`
- `google_ads_search_terms_90d.csv`: ad group fields plus `search_term`
- `google_ads_landing_pages_90d.csv`: ad group fields plus `landing_page_url`

`cost` must be converted from micros into normal currency units.

### Shopify

- `shopify_orders_90d.csv`: `created_at`, `date`, `order_id`, `order_name`, `currency`, `subtotal_price`, `total_price`, `total_tax`, `financial_status`, `fulfillment_status`, `source_name`, `landing_site`, `referring_site`
- `shopify_sales_by_day_90d.csv`: `date`, `orders`, `total_sales`. This file is required for weekly reports because it must include zero-order days; without it the pipeline cannot distinguish "no orders" from "Shopify data was not fetched."
- Optional connector materialization: `shopify_sales_by_order_90d.csv`, `shopify_sales_by_product_90d.csv`

## Weekly Coverage Contract

Weekly reports must be generated only for a date window covered by all four core sources:

- GA4: at least one row for each report date in `ga4_channel_90d.csv`.
- Shopify: one row for each report date in `shopify_sales_by_day_90d.csv`, including days with `orders = 0`.
- Google Ads: at least one row for each report date in `google_ads_ad_group_90d.csv`.
- GSC: at least one row for each report date in `gsc_90d.csv`.

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
- Ad spend, ad clicks, ad conversions, ad conversion value: Google Ads.
- SEO impressions, clicks, CTR, average position: GSC.
- Store conversion rate: Shopify orders divided by GA4 sessions.
- Sitewide ROI: Shopify revenue divided by total Google Ads cost for the same aligned period.
- Add-to-cart rate: GA4 `add_to_cart` events divided by GA4 sessions for the same report period.
- Cart-to-checkout rate: GA4 `begin_checkout` events divided by GA4 `add_to_cart` events for the same report period.
- ROAS: Google Ads conversion value divided by Google Ads cost.
- CPA: Google Ads cost divided by Google Ads conversions; show `n/a` when conversions are zero.

The weekly JSON must persist `site_roi` for current and previous periods. The core KPI table must include GSC clicks, impressions, and CTR.
