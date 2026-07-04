from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from config import DATA_PROCESSED_DIR, DATA_RAW_DIR, PROJECT_ROOT, setup_logging


LOGGER = setup_logging("build_owner_dashboard")
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
WORK_DIR = PROJECT_ROOT / "work"


def money(value: float) -> str:
    return f"${value:,.2f}"


def number(value: float) -> str:
    return f"{value:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def safe_float(value) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if pd.isna(value):
        return None
    return value


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        LOGGER.warning("Missing file: %s", path)
        return pd.DataFrame()
    return pd.read_csv(path)


def shorten_url(value: str) -> str:
    text = str(value or "")
    if len(text) <= 86:
        return text
    return text[:82] + "..."


def build_data() -> dict:
    channel = read_csv(DATA_PROCESSED_DIR / "channel_performance.csv")
    landing = read_csv(DATA_PROCESSED_DIR / "landing_page_performance.csv")
    ads = read_csv(DATA_PROCESSED_DIR / "google_ads_diagnosis.csv")
    queries = read_csv(DATA_PROCESSED_DIR / "search_query_opportunities.csv")
    shopify_orders = read_csv(DATA_RAW_DIR / "shopify_orders_90d.csv")

    shopify = channel[channel["source"] == "Shopify"].copy() if not channel.empty else pd.DataFrame()
    google_ads = channel[channel["source"] == "Google Ads"].copy() if not channel.empty else pd.DataFrame()
    ga4 = channel[channel["source"] == "GA4"].copy() if not channel.empty else pd.DataFrame()

    revenue = safe_float(shopify["revenue"].sum()) if not shopify.empty else safe_float(ga4["revenue"].sum())
    orders = safe_float(shopify["orders"].sum()) if not shopify.empty else safe_float(ga4["orders"].sum())
    sessions = safe_float(ga4["sessions"].sum())
    store_cvr = orders / sessions if sessions else 0.0
    aov = revenue / orders if orders else 0.0
    ads_spend = safe_float(google_ads["cost"].sum()) if not google_ads.empty else 0.0
    ads_value = safe_float(google_ads["revenue"].sum()) if not google_ads.empty else 0.0
    ads_roas = ads_value / ads_spend if ads_spend else 0.0
    ads_events = safe_float(google_ads["conversions"].sum()) if not google_ads.empty else 0.0
    ads_cpa = ads_spend / ads_events if ads_events else 0.0

    kpis = [
        {"metric": "Shopify 收入", "value": revenue, "display": money(revenue), "note": "90 天真实订单口径"},
        {"metric": "订单数", "value": orders, "display": number(orders), "note": "Shopify Analytics"},
        {"metric": "全站转化率", "value": store_cvr, "display": pct(store_cvr), "note": "订单 / GA4 Sessions"},
        {"metric": "Google Ads ROAS", "value": ads_roas, "display": f"{ads_roas:.2f}", "note": "广告转化价值 / 花费"},
    ]

    executive = [
        {"item": "核心判断", "status": "收入口径已接 Shopify，广告已接 Google Ads", "detail": f"90 天 {number(sessions)} sessions 只产生 {number(orders)} 单，真实站点转化率 {pct(store_cvr)}。"},
        {"item": "最大风险", "status": "广告花费高于 Shopify 收入", "detail": f"Google Ads 花费 {money(ads_spend)}，Shopify 收入 {money(revenue)}，需要先排查转化追踪和落地页承接。"},
        {"item": "下周抓手", "status": "先改落地页与广告结构", "detail": "优先处理高点击低加购页面、高花费低转化广告组，再做 SEO 标题与内容补强。"},
    ]

    if not ga4.empty:
        ga4_channels = ga4[["channel", "sessions", "orders", "revenue", "conversion_rate"]].copy()
        ga4_channels["conversion_rate_pct"] = ga4_channels["conversion_rate"].astype(float) * 100
        ga4_channels = ga4_channels.sort_values(["revenue", "sessions"], ascending=False).head(8)
    else:
        ga4_channels = pd.DataFrame(columns=["channel", "sessions", "orders", "revenue", "conversion_rate_pct"])

    ad_efficiency = ads.copy()
    if not ad_efficiency.empty:
        ad_efficiency["diagnosis"] = ad_efficiency["diagnosis"].fillna("ok")
        ad_efficiency = ad_efficiency.sort_values("cost", ascending=False).head(8)
        ad_efficiency = ad_efficiency[["campaign_name", "ad_group_name", "cost", "clicks", "conversion_value", "roas", "diagnosis"]]
    else:
        ad_efficiency = pd.DataFrame(columns=["campaign_name", "ad_group_name", "cost", "clicks", "conversion_value", "roas", "diagnosis"])

    weak_pages = landing.copy()
    if not weak_pages.empty:
        weak_pages["diagnosis"] = weak_pages["diagnosis"].fillna("")
        weak_pages = weak_pages[weak_pages["diagnosis"] == "high_click_low_add_to_cart"].copy()
        weak_pages["traffic"] = weak_pages["ad_clicks"].fillna(0).where(weak_pages["ad_clicks"].fillna(0) > 0, weak_pages["sessions"].fillna(0))
        weak_pages["add_to_cart_rate_pct"] = weak_pages["add_to_cart_rate"].fillna(0).astype(float) * 100
        weak_pages["landing_page_short"] = weak_pages["landing_page_url"].map(shorten_url)
        weak_pages = weak_pages.sort_values(["ad_cost", "traffic"], ascending=False).head(8)
        weak_pages = weak_pages[["landing_page_short", "traffic", "ad_cost", "add_to_cart", "add_to_cart_rate_pct", "orders", "revenue"]]
    else:
        weak_pages = pd.DataFrame(columns=["landing_page_short", "traffic", "ad_cost", "add_to_cart", "add_to_cart_rate_pct", "orders", "revenue"])

    seo_low_ctr = queries[queries["opportunity_type"] == "high_impression_low_ctr"].copy() if not queries.empty else pd.DataFrame()
    if not seo_low_ctr.empty:
        seo_low_ctr["ctr_pct"] = seo_low_ctr["ctr"].astype(float) * 100
        seo_low_ctr = seo_low_ctr.sort_values("impressions", ascending=False).head(10)
        seo_low_ctr = seo_low_ctr[["query", "page", "impressions", "clicks", "ctr_pct", "position"]]
    else:
        seo_low_ctr = pd.DataFrame(columns=["query", "page", "impressions", "clicks", "ctr_pct", "position"])

    seo_rank = queries[queries["opportunity_type"] == "rank_4_20"].copy() if not queries.empty else pd.DataFrame()
    if not seo_rank.empty:
        seo_rank["ctr_pct"] = seo_rank["ctr"].astype(float) * 100
        seo_rank = seo_rank.sort_values(["impressions", "position"], ascending=[False, True]).head(12)
        seo_rank = seo_rank[["query", "page", "impressions", "clicks", "ctr_pct", "position"]]
    else:
        seo_rank = pd.DataFrame(columns=["query", "page", "impressions", "clicks", "ctr_pct", "position"])

    order_rows = []
    if not shopify_orders.empty:
        order_rows = shopify_orders[["date", "order_name", "total_price", "financial_status", "fulfillment_status"]].to_dict("records")

    return {
        "kpis": kpis,
        "executive": executive,
        "channel": ga4_channels.to_dict("records"),
        "ad_efficiency": ad_efficiency.to_dict("records"),
        "weak_pages": weak_pages.to_dict("records"),
        "seo_low_ctr": seo_low_ctr.to_dict("records"),
        "seo_rank": seo_rank.to_dict("records"),
        "orders": json_safe(order_rows),
        "summary": {
            "revenue": revenue,
            "orders": orders,
            "sessions": sessions,
            "store_cvr": store_cvr,
            "aov": aov,
            "ads_spend": ads_spend,
            "ads_value": ads_value,
            "ads_roas": ads_roas,
            "ads_events": ads_events,
            "ads_cpa": ads_cpa,
        },
    }


def build_manifest_snapshot(data: dict) -> dict:
    generated_at = date.today().isoformat()
    manifest = {
        "version": 1,
        "surface": "dashboard",
        "title": "独立站增长诊断系统",
        "description": "老板版 90 天增长诊断：真实收入、转化率、广告效率、落地页断点和 SEO 机会。",
        "generatedAt": generated_at,
        "sources": [
            {"id": "channel", "label": "Processed channel performance", "path": "data/processed/channel_performance.csv"},
            {"id": "landing", "label": "Processed landing page performance", "path": "data/processed/landing_page_performance.csv"},
            {"id": "ads", "label": "Processed Google Ads diagnosis", "path": "data/processed/google_ads_diagnosis.csv"},
            {"id": "queries", "label": "Processed search query opportunities", "path": "data/processed/search_query_opportunities.csv"},
            {"id": "shopify", "label": "Shopify sales by order", "path": "data/raw/shopify_sales_by_order_90d.csv"},
        ],
        "cards": [
            {"id": "revenue", "dataset": "summary", "metrics": [{"label": "Shopify 收入", "field": "revenue", "format": "currency"}, {"label": "订单数", "field": "orders", "format": "number"}]},
            {"id": "orders", "dataset": "summary", "metrics": [{"label": "订单数", "field": "orders", "format": "number"}, {"label": "AOV", "field": "aov", "format": "currency"}]},
            {"id": "store_cvr", "dataset": "summary", "metrics": [{"label": "全站转化率", "field": "store_cvr", "format": "percent"}, {"label": "Sessions", "field": "sessions", "format": "number"}]},
            {"id": "ads_roas", "dataset": "summary", "metrics": [{"label": "Google Ads ROAS", "field": "ads_roas", "format": "number"}, {"label": "广告花费", "field": "ads_spend", "format": "currency"}]},
        ],
        "charts": [
            {
                "id": "channel_sessions",
                "title": "流量主要来自哪里",
                "dataset": "channel",
                "type": "bar",
                "encodings": {"x": {"field": "channel"}, "y": {"field": "sessions"}},
                "source": {"path": "data/processed/channel_performance.csv", "query": {"description": "GA4 channel sessions for latest 90 days", "language": "sql", "engine": "duckdb", "sql": "SELECT channel, sessions, orders, revenue, conversion_rate * 100 AS conversion_rate_pct FROM read_csv_auto('data/processed/channel_performance.csv') WHERE source = 'GA4' ORDER BY sessions DESC LIMIT 6;", "tables_used": ["data/processed/channel_performance.csv"], "filters": ["source = GA4"], "metric_definitions": ["sessions = GA4 sessions summed over latest 90 days", "conversion_rate_pct = ecommerce purchases divided by sessions, expressed in percentage points"]}},
            },
            {
                "id": "ads_cost_roas",
                "title": "广告组花费与 ROAS",
                "dataset": "ad_efficiency",
                "type": "bar",
                "encodings": {"x": {"field": "ad_group_name"}, "y": {"field": "cost"}},
                "source": {"path": "data/processed/google_ads_diagnosis.csv", "query": {"description": "Top Google Ads ad groups by spend", "language": "sql", "engine": "duckdb", "sql": "SELECT campaign_name, ad_group_name, cost, clicks, conversion_value, roas, COALESCE(diagnosis, 'ok') AS diagnosis FROM read_csv_auto('data/processed/google_ads_diagnosis.csv') ORDER BY cost DESC LIMIT 8;", "tables_used": ["data/processed/google_ads_diagnosis.csv"], "filters": ["latest 90 days"], "metric_definitions": ["cost = Google Ads metrics.cost_micros divided by 1,000,000", "roas = conversion_value divided by cost"]}},
            },
            {
                "id": "weak_pages",
                "title": "高流量低加购落地页",
                "dataset": "weak_pages",
                "type": "bar",
                "encodings": {"x": {"field": "landing_page_short"}, "y": {"field": "traffic"}},
                "source": {"path": "data/processed/landing_page_performance.csv", "query": {"description": "Landing pages flagged as high traffic and low add to cart", "language": "sql", "engine": "duckdb", "sql": "SELECT landing_page_url AS landing_page_short, CASE WHEN ad_clicks > 0 THEN ad_clicks ELSE sessions END AS traffic, ad_cost, add_to_cart, add_to_cart_rate * 100 AS add_to_cart_rate_pct, orders FROM read_csv_auto('data/processed/landing_page_performance.csv') WHERE diagnosis = 'high_click_low_add_to_cart' ORDER BY ad_cost DESC, traffic DESC LIMIT 8;", "tables_used": ["data/processed/landing_page_performance.csv"], "filters": ["diagnosis = high_click_low_add_to_cart"], "metric_definitions": ["traffic = ad clicks when available, otherwise GA4 sessions", "add_to_cart_rate_pct = add_to_cart divided by traffic, expressed in percentage points"]}},
            },
        ],
        "tables": [
            {
                "id": "actions",
                "title": "下周优先动作",
                "dataset": "executive",
                "columns": [
                    {"field": "item", "label": "模块", "type": "text"},
                    {"field": "status", "label": "判断", "type": "text"},
                    {"field": "detail", "label": "动作说明", "type": "text"},
                ],
                "defaultSort": {"field": "item", "direction": "asc"},
                "source": {"path": "outputs/owner_growth_diagnosis_summary.json", "query": {"description": "Executive action table derived from reviewed GA4, Shopify, Google Ads, and GSC outputs", "language": "sql", "engine": "duckdb", "sql": "SELECT item, status, detail FROM executive_actions ORDER BY item;", "tables_used": ["data/processed/channel_performance.csv", "data/processed/landing_page_performance.csv", "data/processed/google_ads_diagnosis.csv", "data/processed/search_query_opportunities.csv"], "filters": ["latest 90 days"], "metric_definitions": ["priority actions are rule-based summaries from source-backed diagnostic flags"]}},
            },
            {
                "id": "seo_rank",
                "title": "SEO 机会词：排名 4-20",
                "dataset": "seo_rank",
                "columns": [
                    {"field": "query", "label": "关键词", "type": "text"},
                    {"field": "impressions", "label": "曝光", "type": "number"},
                    {"field": "clicks", "label": "点击", "type": "number"},
                    {"field": "ctr_pct", "label": "CTR %", "type": "number"},
                    {"field": "position", "label": "排名", "type": "number"},
                ],
                "defaultSort": {"field": "impressions", "direction": "desc"},
                "source": {"path": "data/processed/search_query_opportunities.csv", "query": {"description": "GSC queries ranking 4 to 20", "language": "sql", "engine": "duckdb", "sql": "SELECT query, page, impressions, clicks, ctr * 100 AS ctr_pct, position FROM read_csv_auto('data/processed/search_query_opportunities.csv') WHERE opportunity_type = 'rank_4_20' ORDER BY impressions DESC, position ASC LIMIT 12;", "tables_used": ["data/processed/search_query_opportunities.csv"], "filters": ["opportunity_type = rank_4_20"], "metric_definitions": ["ctr_pct = GSC clicks divided by impressions, expressed in percentage points", "position = average GSC ranking position"]}},
            },
        ],
        "blocks": [
            {"id": "intro", "type": "markdown", "body": "# 独立站增长诊断系统\n老板版 90 天看板：先看经营结果，再看广告效率和页面断点。转化率统一按百分比呈现。"},
            {"id": "kpi_strip", "type": "metric-strip", "cardIds": ["revenue", "orders", "store_cvr", "ads_roas"]},
            {"id": "judgement", "type": "markdown", "body": "## 核心判断\n- 真实 Shopify 口径：收入 $1,297.41，订单 7 单，全站转化率 0.10%。\n- Google Ads 花费 $4,095.04，ROAS 1.12，短期重点不是继续加预算，而是先修落地页和追踪口径。\n- 搜索侧已有品牌和品类机会词，但页面 CTR 与排名仍有明显提升空间。"},
            {"id": "channel_sessions_block", "type": "chart", "chartId": "channel_sessions"},
            {"id": "ads_cost_block", "type": "chart", "chartId": "ads_cost_roas"},
            {"id": "weak_pages_block", "type": "chart", "chartId": "weak_pages"},
            {"id": "actions_block", "type": "table", "tableId": "actions"},
            {"id": "seo_rank_block", "type": "table", "tableId": "seo_rank"},
        ],
    }
    snapshot = {
        "version": 1,
        "status": "ready",
        "generatedAt": generated_at,
        "datasets": {
            "summary": [data["summary"]],
            "kpis": data["kpis"],
            "executive": data["executive"],
            "channel": data["channel"],
            "ad_efficiency": data["ad_efficiency"],
            "weak_pages": data["weak_pages"],
            "seo_low_ctr": data["seo_low_ctr"],
            "seo_rank": data["seo_rank"],
            "orders": data["orders"],
        },
    }
    return {"manifest": manifest, "snapshot": snapshot}


def bar_rows(rows: list[dict], label: str, value: str, fmt=lambda x: str(x), color: str = "#2563eb") -> str:
    max_value = max([safe_float(row.get(value)) for row in rows] + [1])
    parts = []
    for row in rows:
        width = safe_float(row.get(value)) / max_value * 100 if max_value else 0
        parts.append(
            f"""
            <div class="bar-row">
              <div class="bar-label" title="{row.get(label, '')}">{row.get(label, '')}</div>
              <div class="bar-track"><div class="bar-fill" style="width:{width:.2f}%; background:{color}"></div></div>
              <div class="bar-value">{fmt(safe_float(row.get(value)))}</div>
            </div>
            """
        )
    return "\n".join(parts)


def build_html(data: dict) -> str:
    s = data["summary"]
    channel_rows = data["channel"]
    ad_rows = data["ad_efficiency"]
    page_rows = data["weak_pages"]
    seo_rank = data["seo_rank"][:8]
    seo_low_ctr = data["seo_low_ctr"][:6]
    actions = data["executive"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>独立站增长诊断系统</title>
  <style>
    :root {{
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #15202b;
      --muted: #667085;
      --line: #d9dee8;
      --blue: #2563eb;
      --gold: #b7791f;
      --rose: #c2415b;
      --green: #147d64;
      --shadow: 0 10px 28px rgba(18, 33, 61, .08);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1280px; margin: 0 auto; padding: 28px; }}
    header {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-end; margin-bottom: 20px; }}
    h1 {{ font-size: 30px; margin: 0 0 6px; letter-spacing: 0; }}
    h2 {{ font-size: 17px; margin: 0 0 14px; }}
    .sub {{ color: var(--muted); }}
    .badge {{ border: 1px solid var(--line); background: #fff; padding: 8px 12px; border-radius: 8px; color: var(--muted); white-space: nowrap; }}
    .grid {{ display: grid; gap: 16px; }}
    .kpis {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 16px; }}
    .two {{ grid-template-columns: 1.1fr .9fr; }}
    .three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; box-shadow: var(--shadow); min-width: 0; }}
    .kpi-label {{ color: var(--muted); margin-bottom: 6px; }}
    .kpi-value {{ font-size: 28px; font-weight: 750; letter-spacing: 0; }}
    .kpi-note {{ margin-top: 6px; color: var(--muted); font-size: 12px; }}
    .callout {{ border-left: 4px solid var(--blue); background: #f3f7ff; }}
    .warn {{ border-left-color: var(--rose); background: #fff5f6; }}
    .good {{ border-left-color: var(--green); background: #f2fbf8; }}
    .bar-row {{ display: grid; grid-template-columns: minmax(160px, 260px) 1fr 86px; gap: 10px; align-items: center; margin: 10px 0; }}
    .bar-label {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #344054; }}
    .bar-track {{ height: 12px; background: #eef2f7; border-radius: 999px; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 999px; }}
    .bar-value {{ text-align: right; font-variant-numeric: tabular-nums; color: #344054; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; border-bottom: 1px solid var(--line); padding: 9px 8px; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 650; }}
    td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .section {{ margin-top: 16px; }}
    .pill {{ display: inline-block; padding: 3px 8px; border-radius: 999px; background: #eef2ff; color: #1d4ed8; font-size: 12px; }}
    .risk {{ background: #fff1f2; color: #be123c; }}
    .ok {{ background: #ecfdf5; color: #047857; }}
    .footer {{ margin-top: 18px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 900px) {{
      .kpis, .two, .three {{ grid-template-columns: 1fr; }}
      header {{ display: block; }}
      .badge {{ display: inline-block; margin-top: 12px; }}
      .bar-row {{ grid-template-columns: 1fr; }}
      .bar-value {{ text-align: left; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>独立站增长诊断系统</h1>
        <div class="sub">老板版 90 天看板 · 数据源：Shopify / GA4 / Google Ads / GSC · 生成日期 {date.today().isoformat()}</div>
      </div>
      <div class="badge">转化率显示规则：订单 ÷ Sessions = {pct(s["store_cvr"])}</div>
    </header>

    <section class="grid kpis">
      <div class="card"><div class="kpi-label">Shopify 收入</div><div class="kpi-value">{money(s["revenue"])}</div><div class="kpi-note">真实订单销售口径</div></div>
      <div class="card"><div class="kpi-label">订单数</div><div class="kpi-value">{number(s["orders"])}</div><div class="kpi-note">90 天订单</div></div>
      <div class="card"><div class="kpi-label">全站转化率</div><div class="kpi-value">{pct(s["store_cvr"])}</div><div class="kpi-note">Shopify 订单 / GA4 Sessions</div></div>
      <div class="card"><div class="kpi-label">Google Ads ROAS</div><div class="kpi-value">{s["ads_roas"]:.2f}</div><div class="kpi-note">花费 {money(s["ads_spend"])}，转化价值 {money(s["ads_value"])}</div></div>
    </section>

    <section class="grid three">
      <div class="card callout"><h2>核心判断</h2><p>90 天 {number(s["sessions"])} sessions 只产生 {number(s["orders"])} 单，真实转化率只有 <b>{pct(s["store_cvr"])}</b>。当前主要问题不是单纯缺流量，而是流量到订单之间的承接断点。</p></div>
      <div class="card warn"><h2>最大风险</h2><p>Google Ads 花费 <b>{money(s["ads_spend"])}</b>，高于 Shopify 90 天收入 <b>{money(s["revenue"])}</b>。需要优先确认广告转化事件是否混入微转化，并修正低加购页面。</p></div>
      <div class="card good"><h2>下周动作</h2><p>先处理高花费低转化广告组，再优化高点击低加购落地页；SEO 侧优先从排名 4-20 的品牌/品类词做标题与内容补强。</p></div>
    </section>

    <section class="grid two section">
      <div class="card"><h2>GA4 渠道 Sessions</h2>{bar_rows(channel_rows, "channel", "sessions", lambda x: number(x), "#2563eb")}</div>
      <div class="card"><h2>渠道订单与收入</h2><table><thead><tr><th>渠道</th><th class="num">Sessions</th><th class="num">订单</th><th class="num">转化率</th><th class="num">收入</th></tr></thead><tbody>
        {''.join(f'<tr><td>{r.get("channel","")}</td><td class="num">{number(safe_float(r.get("sessions")))}</td><td class="num">{number(safe_float(r.get("orders")))}</td><td class="num">{safe_float(r.get("conversion_rate_pct")):.2f}%</td><td class="num">{money(safe_float(r.get("revenue")))}</td></tr>' for r in channel_rows)}
      </tbody></table></div>
    </section>

    <section class="grid two section">
      <div class="card"><h2>Google Ads 花费排行</h2>{bar_rows(ad_rows, "ad_group_name", "cost", lambda x: money(x), "#b7791f")}</div>
      <div class="card"><h2>广告组诊断</h2><table><thead><tr><th>广告系列 / 广告组</th><th class="num">花费</th><th class="num">ROAS</th><th>状态</th></tr></thead><tbody>
        {''.join(f'<tr><td>{r.get("campaign_name","")}<br><span class="sub">{r.get("ad_group_name","")}</span></td><td class="num">{money(safe_float(r.get("cost")))}</td><td class="num">{safe_float(r.get("roas")):.2f}</td><td><span class="pill {"risk" if r.get("diagnosis") != "ok" else "ok"}">{r.get("diagnosis")}</span></td></tr>' for r in ad_rows)}
      </tbody></table></div>
    </section>

    <section class="card section">
      <h2>高点击低加购落地页</h2>
      <table><thead><tr><th>落地页</th><th class="num">流量/点击</th><th class="num">广告花费</th><th class="num">加购率</th><th class="num">订单</th></tr></thead><tbody>
      {''.join(f'<tr><td>{r.get("landing_page_short","")}</td><td class="num">{number(safe_float(r.get("traffic")))}</td><td class="num">{money(safe_float(r.get("ad_cost")))}</td><td class="num">{safe_float(r.get("add_to_cart_rate_pct")):.2f}%</td><td class="num">{number(safe_float(r.get("orders")))}</td></tr>' for r in page_rows)}
      </tbody></table>
    </section>

    <section class="grid two section">
      <div class="card"><h2>SEO 高曝光低 CTR</h2><table><thead><tr><th>关键词</th><th class="num">曝光</th><th class="num">CTR</th><th class="num">排名</th></tr></thead><tbody>
        {''.join(f'<tr><td>{r.get("query","")}</td><td class="num">{number(safe_float(r.get("impressions")))}</td><td class="num">{safe_float(r.get("ctr_pct")):.2f}%</td><td class="num">{safe_float(r.get("position")):.1f}</td></tr>' for r in seo_low_ctr)}
      </tbody></table></div>
      <div class="card"><h2>SEO 排名 4-20 机会词</h2><table><thead><tr><th>关键词</th><th class="num">曝光</th><th class="num">CTR</th><th class="num">排名</th></tr></thead><tbody>
        {''.join(f'<tr><td>{r.get("query","")}</td><td class="num">{number(safe_float(r.get("impressions")))}</td><td class="num">{safe_float(r.get("ctr_pct")):.2f}%</td><td class="num">{safe_float(r.get("position")):.1f}</td></tr>' for r in seo_rank)}
      </tbody></table></div>
    </section>

    <section class="card section">
      <h2>下周优先级</h2>
      <table><thead><tr><th>模块</th><th>判断</th><th>动作说明</th></tr></thead><tbody>
        {''.join(f'<tr><td>{r["item"]}</td><td>{r["status"]}</td><td>{r["detail"]}</td></tr>' for r in actions)}
      </tbody></table>
    </section>

    <div class="footer">说明：Google Ads conversions 当前按广告平台“转化事件”呈现，可能包含微转化；老板版真实成交转化率使用 Shopify 订单 / GA4 Sessions。</div>
  </div>
</body>
</html>"""


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    data = build_data()
    artifact = build_manifest_snapshot(data)
    html = build_html(data)

    html_path = OUTPUTS_DIR / "owner_growth_diagnosis_dashboard.html"
    artifact_path = WORK_DIR / "owner_growth_diagnosis_artifact.json"
    summary_path = OUTPUTS_DIR / "owner_growth_diagnosis_summary.json"

    html_path.write_text(html, encoding="utf-8")
    artifact_path.write_text(json.dumps(json_safe(artifact), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    summary_path.write_text(json.dumps(json_safe(data["summary"]), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    LOGGER.info("HTML dashboard written: %s", html_path)
    LOGGER.info("Artifact payload written: %s", artifact_path)
    LOGGER.info("Summary JSON written: %s", summary_path)


if __name__ == "__main__":
    main()
