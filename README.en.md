# DTC Growth Data Report Skill

[中文说明（默认）](README.md)

Codex skill for building reusable independent-store growth reporting systems that connect GA4, Google Search Console, Google Ads, and Shopify data.

This skill helps Codex set up and customize a local data pipeline for ecommerce growth diagnostics, weekly boss reports, channel performance, landing page performance, Google Ads efficiency, SEO opportunities, and Shopify revenue/order analysis.

## What It Includes

- GA4 fetch script for channel, landing page, and dated `add_to_cart` / `begin_checkout` funnel performance.
- Google Search Console fetch script that separates property-level daily KPIs from query/page SEO detail, avoiding anonymous-query and page-aggregation undercounts.
- Google Ads fetch script for campaign, ad group, search term, and landing page data.
- Shopify Admin API fetch script with static-token or client-credentials authentication, GA4 Property timezone date alignment, paid/non-test/non-cancelled filtering, and a daily sales file that includes zero-order days.
- Transform script that unifies raw source files into processed CSVs.
- Weekly comparison report generator with current week vs previous week.
- Operator-ready weekly report modules: business conclusions, revenue bridge, funnel health, Google Ads budget actions, page actions, SEO intent clusters, anomaly alerts, next-week owners, and data health checks.
- Weekly funnel comparisons use dated GA4 add-to-cart and checkout events instead of a 90-day proxy total.
- Purchase-integrity health compares only Online Store browser orders with GA4 purchases/revenue, reports Shop/POS/app/offsite orders separately while retaining them in Shopify business totals, escalates residual gaps to transaction-level BigQuery reconciliation, and never auto-sends recovery events.
- Boss-facing HTML dashboard generator.
- Configuration and data contract references.

## Install

Copy the skill folder into your Codex skills directory:

```bash
cp -R dtc-growth-data-report ~/.codex/skills/
```

Restart Codex or start a new Codex session so the skill can be discovered.

## Use

Example prompt:

```text
Use $dtc-growth-data-report to connect GA4, GSC, Google Ads, and Shopify data, then build a weekly growth report.
```

For a new project, ask Codex:

```text
Use $dtc-growth-data-report to install the growth reporting pipeline into this project and generate a boss-facing weekly report.
```

## Required Configuration

Create `.env` from the included `.env.example` in your project. Required credentials depend on the sources you want to connect:

- GA4: service account JSON path, GA4 property ID, and exact IANA Property timezone.
- GSC: service account JSON path and Search Console property URL.
- Google Ads: developer token, OAuth client ID/secret, refresh token, customer ID, and optional manager account ID.
- Shopify: shop domain, API version, and either an Admin API access token or client ID/client secret.

Never commit `.env` or credential JSON files.

## Default Outputs

The installed pipeline writes:

- `data/raw/`: raw GA4, GSC, Google Ads, and Shopify CSV files.
- `data/raw/gsc_daily_90d.csv`: property-level GSC daily totals used for weekly KPIs and coverage.
- `data/raw/shopify_sales_by_day_90d.csv`: Shopify daily orders and revenue, including zero-order days, used to verify source coverage.
- `data/processed/channel_performance.csv`
- `data/processed/landing_page_performance.csv`
- `data/processed/google_ads_diagnosis.csv`
- `data/processed/search_query_opportunities.csv`
- `reports/weekly_growth_diagnosis.md`
- `outputs/weekly_growth_report_template.html`
- `outputs/weekly_growth_report_template.md`
- `outputs/weekly_growth_report_template.json`

## Weekly Report Data Completeness

All four source fetches are a strict precondition. If authentication, permission, configuration, dependency, network, quota, or code errors break a fetch, repair the cause and rerun the source before transformation or report generation. Never publish a weekly report by silently reusing stale raw data. If user-only authorization is required, stop and report that exact action.

Weekly reports are generated only for the latest 7-day period that is covered by all four core sources: GA4, Shopify, Google Ads, and GSC. The previous 7 days must also be covered for week-over-week comparison.

If one source is delayed, the report window moves back until all four sources align. If no aligned window exists, the generator fails with source/date gaps instead of producing a partial report.

The weekly report is designed as an operating brief, not only a metric export. It translates source data into budget moves, page fixes, SEO priorities, owner-ready next actions, and tracking health checks.

The top cards include sitewide ROI (`Shopify revenue / Google Ads spend`). The core KPI table includes GSC clicks alongside impressions and CTR.

GSC sitewide KPIs come from the `date` + `byProperty` daily export; query/page rows are used only for SEO opportunities. Shopify business totals include all paid, non-test, non-cancelled orders, while GA4 purchase integrity compares only Online Store browser orders and reports offsite orders separately.

## Repository Topics

Recommended GitHub topics:

`codex-skill`, `dtc`, `ecommerce`, `shopify`, `ga4`, `google-search-console`, `google-ads`, `growth-analytics`, `marketing-analytics`, `weekly-report`
