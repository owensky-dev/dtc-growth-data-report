# Data Contract

## Raw Files

The standard pipeline writes raw source files to `data/raw/`.

### GA4

- `ga4_channel_90d.csv`: `date`, `sessionDefaultChannelGroup`, `sessions`, `engagedSessions`, `conversions`, `ecommercePurchases`, `totalRevenue`
- `ga4_landing_pages_90d.csv`: `landingPagePlusQueryString`, `landing_page_url`, `sessions`, `engagedSessions`, `conversions`, `ecommercePurchases`, `totalRevenue`
- `ga4_landing_page_events_90d.csv`: `landingPagePlusQueryString`, `landing_page_url`, `eventName`, `eventCount`

### GSC

- `gsc_90d.csv`: `date`, `page`, `query`, `country`, `device`, `clicks`, `impressions`, `ctr`, `position`

### Google Ads

- `google_ads_ad_group_90d.csv`: `date`, `campaign_id`, `campaign_name`, `ad_group_id`, `ad_group_name`, `impressions`, `clicks`, `cost`, `conversions`, `conversion_value`
- `google_ads_search_terms_90d.csv`: ad group fields plus `search_term`
- `google_ads_landing_pages_90d.csv`: ad group fields plus `landing_page_url`

`cost` must be converted from micros into normal currency units.

### Shopify

- `shopify_orders_90d.csv`: `created_at`, `date`, `order_id`, `order_name`, `currency`, `subtotal_price`, `total_price`, `total_tax`, `financial_status`, `fulfillment_status`, `source_name`, `landing_site`, `referring_site`
- Optional connector materialization: `shopify_sales_by_order_90d.csv`, `shopify_sales_by_product_90d.csv`

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
- ROAS: Google Ads conversion value divided by Google Ads cost.
- CPA: Google Ads cost divided by Google Ads conversions; show `n/a` when conversions are zero.
