# Report Workflows

## Weekly Boss Report

Use `scripts/generate_weekly_comparison_template.py` after raw and processed data are refreshed.

Default comparison:

- Current week: latest complete date minus 6 days through latest complete date.
- Previous week: the 7 days immediately before current week.

Required sections:

- Executive Summary
- Top KPI cards
- Daily Google Ads spend and weekly spend total
- Core KPI table: current week, previous week, change
- Channel traffic changes
- Google Ads diagnosis
- High-click low-add-to-cart landing pages
- High-impression low-CTR SEO queries
- Rank 4-20 SEO opportunity queries
- Next-week priorities
- Data caveats

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
