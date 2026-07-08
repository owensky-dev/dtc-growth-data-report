# Report Workflows

## Weekly Boss Report

Use `scripts/generate_weekly_comparison_template.py` after raw and processed data are refreshed.

Default comparison:

- Current week: latest 7-day period where GA4, Shopify, Google Ads, and GSC all have daily coverage.
- Previous week: the 7 days immediately before current week, also requiring all four sources to have daily coverage.
- If a source is delayed, move the whole report window back until all four sources align. Do not mix a newer GA4/GSC/Ads window with stale Shopify data.
- If no aligned 14-day comparison window exists, stop and report the missing source/date gaps rather than generating a partial report.

Required sections:

- Executive Summary
- Operator conclusions: state the main business judgment and the first operating move.
- Top KPI cards
- Revenue bridge: split revenue movement into traffic, conversion rate, and AOV effects.
- Funnel health: show reach, add-to-cart proxy, Shopify purchases, and ad click-to-conversion efficiency.
- Daily Google Ads spend and weekly spend total
- Core KPI table: current week, previous week, change
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
