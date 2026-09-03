# Report Workflows

## Weekly Boss Report

Use `scripts/generate_weekly_comparison_template.py` after raw and processed data are refreshed.

Strict acquisition gate:

- Run GA4, GSC, Google Ads, and Shopify fetches before transformation.
- If any fetch fails, repair authentication, permissions, configuration, dependencies, network, quota, or code first, then rerun it. Never continue with stale raw data.
- Generate the report only after all four fetches succeed. If user-only authorization is required, stop and report the exact action instead of producing a stale report.
- Use `google_ads_campaign_90d.csv` for totals and campaign decisions. Do not infer account-wide zero conversions from ad-group data because Performance Max may have no traditional ad-group rows.
- Treat source publication delay separately from fetch failure: after successful fetches, move the aligned report window back when a provider has not published the newest day.
- Use GSC property-level daily totals for weekly KPIs and coverage; keep query/page/country/device rows only for SEO opportunity detail.
- Convert Shopify `createdAt` into the GA4 Property timezone before assigning dates, and build daily business totals from paid, non-test, non-cancelled orders.
- Fail closed when order-level paid count/revenue does not reconcile to the Shopify daily table for either comparison week; do not classify a partial raw file as an Online Store/offsite difference.

Default comparison:

- Current week: latest 7-day period where GA4, Shopify, Google Ads, and GSC all have daily coverage.
- Previous week: the 7 days immediately before current week, also requiring all four sources to have daily coverage.
- If a source is delayed, move the whole report window back until all four sources align. Do not mix a newer GA4/GSC/Ads window with stale Shopify data.
- If no aligned 14-day comparison window exists, stop and report the missing source/date gaps rather than generating a partial report.

Required sections:

- Executive Summary
- Operator conclusions: state the main business judgment and the first operating move.
- Top KPI cards: Shopify revenue, orders, store conversion rate, sitewide ROI (`Shopify revenue / Google Ads spend`), and Google Ads ROAS.
- Revenue bridge: split revenue movement into traffic, conversion rate, and AOV effects.
- Funnel health: show GA4 Sessions, dated `add_to_cart`, dated `begin_checkout`, Shopify purchases, and ad click-to-conversion efficiency. Compare GA4 funnel events for the current and previous aligned weeks; do not substitute a 90-day event total when dated data is available.
- Data health: compare Shopify Online Store (`source_name=web`) current-paid count/revenue with GA4 aggregates for the same aligned week as an alert only. Never label that aggregate ratio a tracking rate.
- When `data/processed/purchase_reconciliation.json` exists, require exact period equality, complete BigQuery daily tables, a matching Shopify snapshot, and `reconciliation.publishable=true`. Then show unique-ID purchase capture for the eligible web cohort, current-paid web coverage, refund coverage, Shopify-only/GA4-only/duplicate/blank exceptions, and the amount bridge. Suppress rates when a gate fails.
- Show Shop/POS/draft/app/offsite orders separately while retaining them in Shopify business totals. Put verified transaction exceptions in the Executive Summary and P0 actions; when exact reconciliation is unavailable, label the aggregate issue unverified. Hand authorized recovery to `$ga4-data-analysis`; this report remains read-only.

## Monthly Report Purchase Integrity

- Use the same canonical reconciliation contract for the full calendar month. Require every daily `events_YYYYMMDD` table in the month before publishing purchase/refund coverage rates.
- Keep Shopify monthly business sales/ROI independent from tracking health. Show three separate lines: Shopify business result, web purchase capture, and refund-event coverage.
- Include an amount bridge when aggregate Shopify/GA4 revenue differs. Never let a refunded GA4 purchase offset missing paid purchases without disclosure.
- If month-end BigQuery export is incomplete, generate the business report only if the four core sources are otherwise complete, mark transaction integrity pending, and rerun the reconciliation after the missing daily table arrives.
- Daily Google Ads spend and weekly spend total
- Core KPI table: current week, previous week, and change, including GSC clicks alongside impressions and CTR.
- Channel traffic changes
- Google Ads diagnosis plus budget actions: add budget, reduce budget, or observe.
- Landing page diagnosis plus page-level optimization actions.
- SEO opportunities grouped by search intent, plus high-impression low-CTR and rank 4-20 details.
- Anomaly alerts for changes that need operator attention.
- Next-week action table with priority, owner, target metric, and done condition.
- Data health checks and data caveats.
- Source coverage summary

## Owner Dashboard

Use `scripts/build_owner_dashboard.py` when the user wants a visual, boss-facing overview instead of a narrative weekly report.

Prioritize:

- Revenue, orders, store conversion rate, Google Ads ROAS.
- Channel mix.
- Ad spend risk.
- Landing page friction.
- SEO opportunity tables.

## Custom Diagnostic Report

For a custom request, map user intent to the four-source model:

- Growth health: revenue, orders, sessions, conversion rate, AOV.
- Paid efficiency: spend, clicks, conversions, ROAS, CPA, high-cost low-return campaigns.
- CRO: high-traffic low-add-to-cart or low-purchase landing pages.
- SEO: high-impression low-CTR queries, ranking 4-20 opportunities, paid/organic keyword gaps.
- Cross-channel: SEO keywords worth testing in ads, ad terms worth turning into SEO content.

Always state data windows and limitations. If Google Ads search terms are empty, say so directly rather than inventing keyword recommendations.
