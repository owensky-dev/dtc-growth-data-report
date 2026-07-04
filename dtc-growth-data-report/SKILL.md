---
name: dtc-growth-data-report
description: Build and customize DTC independent-store growth reporting systems that connect GA4, Google Search Console, Google Ads, and Shopify data. Use when the user wants to set up, repair, reuse, share, or run a local reporting pipeline for ecommerce growth diagnostics, weekly boss reports, channel performance, landing page performance, SEO opportunities, Google Ads diagnosis, or Shopify revenue/order analysis.
---

# DTC Growth Data Report

## Core Workflow

Use this skill to create or operate a local four-source DTC reporting system:

1. Check whether the target project already has `scripts/`, `data/raw/`, `data/processed/`, `reports/`, and `outputs/`.
2. If the project is missing the pipeline, install the bundled template with `scripts/install_growth_pipeline.py`.
3. Configure secrets only through `.env` or local config files. Never hard-code or print tokens.
4. Fetch raw data into `data/raw/`.
5. Run `scripts/transform_data.py` to produce unified processed CSV files.
6. Generate the requested report surface: Markdown report, owner dashboard, weekly comparison template, or a custom report.
7. Verify the output files exist and that rates are rendered as percentages.

For setup and required keys, read `references/configuration.md`. For source/processed schemas, read `references/data-contract.md`. For report customization patterns, read `references/report-workflows.md`.

## Install Template Into A Project

When a user asks to reuse or share this system in a new repo, run:

```bash
python /path/to/dtc-growth-data-report/scripts/install_growth_pipeline.py --target /path/to/project
```

This copies:

- `scripts/config.py`
- `scripts/fetch_ga4.py`
- `scripts/fetch_gsc.py`
- `scripts/fetch_google_ads.py`
- `scripts/fetch_shopify.py`
- `scripts/transform_data.py`
- `scripts/generate_report.py`
- `scripts/generate_weekly_comparison_template.py`
- `scripts/build_owner_dashboard.py`
- `requirements.txt`
- `.env.example`

After installing, create `.env` from `.env.example` and ask the user to fill missing secrets. Do not copy an existing `.env` into shareable artifacts.

## Run The Existing Pipeline

Use the project Python environment when available. Otherwise prefer the Codex bundled Python if present:

```bash
/Users/linheping/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/fetch_ga4.py
/Users/linheping/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/fetch_gsc.py
/Users/linheping/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/fetch_google_ads.py
/Users/linheping/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/fetch_shopify.py
/Users/linheping/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/transform_data.py
/Users/linheping/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/generate_weekly_comparison_template.py
```

If a source fetch fails, continue with available raw data when the report can still be generated. State the limitation clearly in the final handoff.

## Custom Report Rules

When customizing reports:

- Use Shopify as the default source of truth for revenue and orders.
- Use GA4 for sessions, engagement, landing page behavior, and funnel events.
- Use Google Ads for spend, clicks, conversions, conversion value, ROAS, CPA, search terms, and ad landing URLs.
- Use GSC for SEO queries, pages, clicks, impressions, CTR, and average position.
- Render conversion rate, CTR, add-to-cart rate, and similar ratios as percentages.
- Compare latest complete 7 days vs previous 7 days for weekly reports unless the user requests another window.
- Keep boss-facing reports concise, Chinese-first by default, and action-oriented.
- Keep raw data in `data/raw/`, transformed data in `data/processed/`, durable reports in `reports/` or `outputs/`.

## Validation Checklist

Before final handoff:

- Confirm `.env` values were read, not hard-coded.
- Confirm required raw and processed files exist.
- Confirm HTML/Markdown reports exist and are non-empty.
- Confirm conversion rates and CTR are percentages, not decimals.
- Confirm Google Ads cost is in account currency units, not micros.
- Confirm no secrets appear in outputs, logs, skill files, or final response.
