from __future__ import annotations

import argparse
import html
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from config import DATA_PROCESSED_DIR, DATA_RAW_DIR, PROJECT_ROOT, setup_logging


LOGGER = setup_logging("generate_weekly_comparison_template")
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REQUIRED_SOURCES = {
    "ga4": "GA4",
    "shopify_daily": "Shopify",
    "ads": "Google Ads",
    "gsc": "GSC",
}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        LOGGER.warning("Missing source file: %s", path)
        return pd.DataFrame()
    frame = pd.read_csv(path)
    LOGGER.info("Loaded %s rows=%s", path.name, len(frame))
    return frame


def parse_ga4_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%Y%m%d", errors="coerce")


def parse_iso_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0)


def metric_sum(frame: pd.DataFrame, column: str) -> float:
    values = numeric(frame, column)
    if values.empty:
        return 0.0
    return float(values.sum())


def money(value: float) -> str:
    return f"${value:,.2f}"


def number(value: float) -> str:
    return f"{value:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp_delta(current: float, previous: float) -> str:
    diff = (current - previous) * 100
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.2f} pp"


def delta_value(current: float, previous: float, is_rate: bool = False) -> dict[str, str]:
    if is_rate:
        diff = (current - previous) * 100
        if abs(diff) < 0.005:
            tone = "flat"
        elif diff > 0:
            tone = "up"
        else:
            tone = "down"
        return {"display": pp_delta(current, previous), "tone": tone}

    if previous == 0 and current == 0:
        return {"display": "0.0%", "tone": "flat"}
    if previous == 0:
        return {"display": "从 0 增至 " + number(current), "tone": "up"}
    change = (current - previous) / abs(previous)
    tone = "flat" if abs(change) < 0.005 else ("up" if change > 0 else "down")
    sign = "+" if change > 0 else ""
    return {"display": f"{sign}{change * 100:.1f}%", "tone": tone}


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def period_filter(frame: pd.DataFrame, date_col: str, start: date, end: date) -> pd.DataFrame:
    if frame.empty or date_col not in frame.columns:
        return pd.DataFrame(columns=frame.columns)
    mask = (frame[date_col].dt.date >= start) & (frame[date_col].dt.date <= end)
    return frame[mask].copy()


def weighted_average(frame: pd.DataFrame, value_col: str, weight_col: str) -> float:
    if frame.empty or value_col not in frame.columns or weight_col not in frame.columns:
        return 0.0
    values = pd.to_numeric(frame[value_col], errors="coerce").fillna(0)
    weights = pd.to_numeric(frame[weight_col], errors="coerce").fillna(0)
    total_weight = float(weights.sum())
    return float((values * weights).sum() / total_weight) if total_weight else 0.0


def source_dates(frame: pd.DataFrame, source_name: str) -> set[date]:
    if frame.empty or "parsed_date" not in frame.columns:
        raise RuntimeError(f"{source_name} 缺少可用日期数据，不能生成四源对齐周报。")
    parsed = frame["parsed_date"].dropna()
    if parsed.empty:
        raise RuntimeError(f"{source_name} 日期列无法解析，不能生成四源对齐周报。")
    return set(parsed.dt.date)


def missing_dates(available: set[date], start: date, end: date) -> list[str]:
    day = start
    missing: list[str] = []
    while day <= end:
        if day not in available:
            missing.append(day.isoformat())
        day += timedelta(days=1)
    return missing


def latest_aligned_period(sources: dict[str, pd.DataFrame]) -> tuple[date, date, date, date, dict[str, Any]]:
    date_sets = {
        key: source_dates(sources[key], label)
        for key, label in REQUIRED_SOURCES.items()
    }
    latest_allowed = min(max(values) for values in date_sets.values())
    latest_allowed = min(latest_allowed, date.today() - timedelta(days=1))
    earliest_allowed = max(min(values) for values in date_sets.values())

    end = latest_allowed
    while end - timedelta(days=13) >= earliest_allowed:
        previous_start = end - timedelta(days=13)
        current_start = end - timedelta(days=6)
        if all(not missing_dates(values, previous_start, end) for values in date_sets.values()):
            coverage = {
                "rule": "latest 7-day period aligned across GA4, Shopify, Google Ads, and GSC; previous 7 days also covered for comparison",
                "sources": {
                    REQUIRED_SOURCES[key]: {
                        "first_date": min(values).isoformat(),
                        "last_date": max(values).isoformat(),
                        "covered_days_in_comparison_window": 14,
                    }
                    for key, values in date_sets.items()
                },
            }
            return current_start, end, previous_start, current_start - timedelta(days=1), coverage
        end -= timedelta(days=1)

    current_start = latest_allowed - timedelta(days=6)
    previous_start = latest_allowed - timedelta(days=13)
    gaps = {
        REQUIRED_SOURCES[key]: missing_dates(values, previous_start, latest_allowed)[:10]
        for key, values in date_sets.items()
        if missing_dates(values, previous_start, latest_allowed)
    }
    raise RuntimeError(
        "找不到 GA4、Shopify、Google Ads、GSC 四源同时覆盖的最新 7 天周报周期；"
        f"检查窗口 {previous_start.isoformat()}..{latest_allowed.isoformat()} 缺口示例：{gaps}"
    )


def summarize_period(
    ga4: pd.DataFrame,
    shopify_daily: pd.DataFrame,
    ads: pd.DataFrame,
    gsc: pd.DataFrame,
    start: date,
    end: date,
) -> dict[str, float]:
    ga4_week = period_filter(ga4, "parsed_date", start, end)
    shopify_week = period_filter(shopify_daily, "parsed_date", start, end)
    ads_week = period_filter(ads, "parsed_date", start, end)
    gsc_week = period_filter(gsc, "parsed_date", start, end)

    sessions = metric_sum(ga4_week, "sessions")
    orders = metric_sum(shopify_week, "orders")
    revenue = metric_sum(shopify_week, "total_sales")
    ad_spend = metric_sum(ads_week, "cost")
    ad_clicks = metric_sum(ads_week, "clicks")
    ad_conversions = metric_sum(ads_week, "conversions")
    ad_value = metric_sum(ads_week, "conversion_value")
    gsc_clicks = metric_sum(gsc_week, "clicks")
    gsc_impressions = metric_sum(gsc_week, "impressions")

    return {
        "revenue": revenue,
        "orders": orders,
        "sessions": sessions,
        "conversion_rate": safe_divide(orders, sessions),
        "aov": safe_divide(revenue, orders),
        "ad_spend": ad_spend,
        "ad_clicks": ad_clicks,
        "ad_conversions": ad_conversions,
        "ad_value": ad_value,
        "roas": safe_divide(ad_value, ad_spend),
        "cpa": safe_divide(ad_spend, ad_conversions),
        "seo_impressions": gsc_impressions,
        "seo_clicks": gsc_clicks,
        "seo_ctr": safe_divide(gsc_clicks, gsc_impressions),
        "seo_position": weighted_average(gsc_week, "position", "impressions"),
    }


def kpi_rows(current: dict[str, float], previous: dict[str, float]) -> list[dict[str, str]]:
    specs = [
        ("Shopify 收入", "revenue", money, False),
        ("订单数", "orders", number, False),
        ("GA4 Sessions", "sessions", number, False),
        ("全站转化率", "conversion_rate", pct, True),
        ("客单价 AOV", "aov", money, False),
        ("Google Ads 花费", "ad_spend", money, False),
        ("Google Ads ROAS", "roas", lambda value: f"{value:.2f}", False),
        ("GSC 曝光", "seo_impressions", number, False),
        ("GSC CTR", "seo_ctr", pct, True),
    ]
    rows: list[dict[str, str]] = []
    for label, key, formatter, is_rate in specs:
        delta = delta_value(current[key], previous[key], is_rate)
        rows.append(
            {
                "metric": label,
                "current": formatter(current[key]),
                "previous": formatter(previous[key]),
                "change": delta["display"],
                "tone": delta["tone"],
            }
        )
    cpa_delta = {"display": "无转化", "tone": "flat"} if current["ad_conversions"] == 0 else delta_value(current["cpa"], previous["cpa"])
    rows.insert(
        7,
        {
            "metric": "Google Ads CPA",
            "current": money(current["cpa"]) if current["ad_conversions"] else "n/a",
            "previous": money(previous["cpa"]) if previous["ad_conversions"] else "n/a",
            "change": cpa_delta["display"],
            "tone": cpa_delta["tone"],
        },
    )
    return rows


def channel_rows(ga4: pd.DataFrame, current_start: date, current_end: date, previous_start: date, previous_end: date) -> list[dict[str, str]]:
    if ga4.empty:
        return []
    current = period_filter(ga4, "parsed_date", current_start, current_end)
    previous = period_filter(ga4, "parsed_date", previous_start, previous_end)
    current_group = current.groupby("sessionDefaultChannelGroup", dropna=False)["sessions"].sum()
    previous_group = previous.groupby("sessionDefaultChannelGroup", dropna=False)["sessions"].sum()
    channels = sorted(set(current_group.index) | set(previous_group.index), key=lambda item: current_group.get(item, 0), reverse=True)
    rows = []
    for channel in channels[:8]:
        cur = float(current_group.get(channel, 0))
        prev = float(previous_group.get(channel, 0))
        delta = delta_value(cur, prev)
        rows.append({"channel": str(channel), "current": number(cur), "previous": number(prev), "change": delta["display"], "tone": delta["tone"]})
    return rows


def ads_rows(ads_raw: pd.DataFrame, current_start: date, current_end: date) -> list[dict[str, str]]:
    current = period_filter(ads_raw, "parsed_date", current_start, current_end)
    if current.empty:
        return []
    grouped = (
        current.groupby(["campaign_name", "ad_group_name"], dropna=False)
        .agg({"cost": "sum", "clicks": "sum", "conversions": "sum", "conversion_value": "sum"})
        .reset_index()
    )
    grouped["roas"] = grouped.apply(lambda row: safe_divide(float(row["conversion_value"]), float(row["cost"])), axis=1)
    grouped["cpa"] = grouped.apply(lambda row: safe_divide(float(row["cost"]), float(row["conversions"])), axis=1)
    grouped = grouped.sort_values(["cost", "roas"], ascending=[False, True]).head(8)
    rows = []
    for _, row in grouped.iterrows():
        rows.append(
            {
                "campaign": str(row["campaign_name"]),
                "ad_group": str(row["ad_group_name"]),
                "cost": money(float(row["cost"])),
                "clicks": number(float(row["clicks"])),
                "conversions": number(float(row["conversions"])),
                "roas": f"{float(row['roas']):.2f}",
                "cpa": money(float(row["cpa"])) if float(row["conversions"]) else "n/a",
            }
        )
    return rows


def daily_ad_spend_rows(ads_raw: pd.DataFrame, current_start: date, current_end: date) -> list[dict[str, Any]]:
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    if ads_raw.empty:
        daily = pd.Series(dtype="float64")
    else:
        current = period_filter(ads_raw, "parsed_date", current_start, current_end)
        if current.empty:
            daily = pd.Series(dtype="float64")
        else:
            daily = current.groupby(current["parsed_date"].dt.date)["cost"].sum()

    rows: list[dict[str, Any]] = []
    day = current_start
    while day <= current_end:
        cost = float(daily.get(day, 0.0))
        rows.append(
            {
                "date": day.isoformat(),
                "weekday": weekdays[day.weekday()],
                "cost": cost,
                "display": money(cost),
            }
        )
        day += timedelta(days=1)
    return rows


def seo_rows(gsc: pd.DataFrame, current_start: date, current_end: date) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    current = period_filter(gsc, "parsed_date", current_start, current_end)
    if current.empty:
        return [], []
    grouped = (
        current.groupby(["query", "page"], dropna=False)
        .agg({"clicks": "sum", "impressions": "sum", "position": "mean"})
        .reset_index()
    )
    grouped["ctr"] = grouped.apply(lambda row: safe_divide(float(row["clicks"]), float(row["impressions"])), axis=1)
    low_ctr = grouped[(grouped["impressions"] >= 50) & (grouped["ctr"] < 0.02)].sort_values("impressions", ascending=False).head(8)
    rank = grouped[(grouped["position"] >= 4) & (grouped["position"] <= 20)].sort_values(["impressions", "position"], ascending=[False, True]).head(8)

    def to_rows(frame: pd.DataFrame) -> list[dict[str, str]]:
        rows = []
        for _, row in frame.iterrows():
            rows.append(
                {
                    "query": str(row["query"]),
                    "impressions": number(float(row["impressions"])),
                    "clicks": number(float(row["clicks"])),
                    "ctr": pct(float(row["ctr"])),
                    "position": f"{float(row['position']):.1f}",
                    "page": shorten(str(row["page"]), 68),
                }
            )
        return rows

    return to_rows(low_ctr), to_rows(rank)


def landing_rows(landing: pd.DataFrame) -> list[dict[str, str]]:
    if landing.empty or "diagnosis" not in landing.columns:
        return []
    weak = landing[landing["diagnosis"] == "high_click_low_add_to_cart"].copy()
    if weak.empty:
        return []
    weak["traffic"] = numeric(weak, "ad_clicks").where(numeric(weak, "ad_clicks") > 0, numeric(weak, "sessions"))
    weak = weak.sort_values(["ad_cost", "traffic"], ascending=False).head(8)
    rows = []
    for _, row in weak.iterrows():
        rows.append(
            {
                "page": shorten(str(row.get("landing_page_url", "")), 86),
                "traffic": number(float(row.get("traffic", 0) or 0)),
                "ad_cost": money(float(row.get("ad_cost", 0) or 0)),
                "add_to_cart_rate": pct(float(row.get("add_to_cart_rate", 0) or 0)),
                "orders": number(float(row.get("orders", 0) or 0)),
            }
        )
    return rows


def shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def html_table(rows: list[dict[str, str]], headers: list[tuple[str, str]]) -> str:
    if not rows:
        return '<p class="empty">暂无数据</p>'
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in headers)
    body_rows = []
    for row in rows:
        cells = []
        for key, _ in headers:
            cls = f' class="{html.escape(row.get("tone", ""))}"' if key == "change" and row.get("tone") else ""
            cells.append(f"<td{cls}>{html.escape(str(row.get(key, '')))}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def markdown_table(rows: list[dict[str, str]], headers: list[tuple[str, str]]) -> str:
    if not rows:
        return "_暂无数据_"
    labels = [label for _, label in headers]
    keys = [key for key, _ in headers]
    lines = ["| " + " | ".join(labels) + " |", "| " + " | ".join(["---"] * len(labels)) + " |"]
    for row in rows:
        values = [str(row.get(key, "")).replace("|", "\\|") for key in keys]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def load_sources() -> dict[str, pd.DataFrame]:
    ga4 = read_csv(DATA_RAW_DIR / "ga4_channel_90d.csv")
    if not ga4.empty and "date" in ga4.columns:
        ga4["parsed_date"] = parse_ga4_date(ga4["date"])

    shopify = read_csv(DATA_RAW_DIR / "shopify_orders_90d.csv")
    if not shopify.empty and "date" in shopify.columns:
        shopify["parsed_date"] = parse_iso_date(shopify["date"])

    shopify_daily = read_csv(DATA_RAW_DIR / "shopify_sales_by_day_90d.csv")
    if not shopify_daily.empty and "date" in shopify_daily.columns:
        shopify_daily["parsed_date"] = parse_iso_date(shopify_daily["date"])

    ads = read_csv(DATA_RAW_DIR / "google_ads_ad_group_90d.csv")
    if not ads.empty and "date" in ads.columns:
        ads["parsed_date"] = parse_iso_date(ads["date"])

    gsc = read_csv(DATA_RAW_DIR / "gsc_90d.csv")
    if not gsc.empty and "date" in gsc.columns:
        gsc["parsed_date"] = parse_iso_date(gsc["date"])

    landing = read_csv(DATA_PROCESSED_DIR / "landing_page_performance.csv")
    return {"ga4": ga4, "shopify": shopify, "shopify_daily": shopify_daily, "ads": ads, "gsc": gsc, "landing": landing}


def build_report_data() -> dict[str, Any]:
    sources = load_sources()
    current_start, end, previous_start, previous_end, coverage = latest_aligned_period(sources)

    current = summarize_period(sources["ga4"], sources["shopify_daily"], sources["ads"], sources["gsc"], current_start, end)
    previous = summarize_period(sources["ga4"], sources["shopify_daily"], sources["ads"], sources["gsc"], previous_start, previous_end)
    low_ctr, rank_opportunities = seo_rows(sources["gsc"], current_start, end)

    data = {
        "generated_at": date.today().isoformat(),
        "current_start": current_start.isoformat(),
        "current_end": end.isoformat(),
        "previous_start": previous_start.isoformat(),
        "previous_end": previous_end.isoformat(),
        "current": current,
        "previous": previous,
        "kpis": kpi_rows(current, previous),
        "channels": channel_rows(sources["ga4"], current_start, end, previous_start, previous_end),
        "ads": ads_rows(sources["ads"], current_start, end),
        "daily_ad_spend": daily_ad_spend_rows(sources["ads"], current_start, end),
        "low_ctr": low_ctr,
        "rank_opportunities": rank_opportunities,
        "weak_landing": landing_rows(sources["landing"]),
        "source_coverage": coverage,
    }
    return data


def build_summary(data: dict[str, Any]) -> list[str]:
    current = data["current"]
    previous = data["previous"]
    revenue_delta = delta_value(current["revenue"], previous["revenue"])["display"]
    cvr_delta = pp_delta(current["conversion_rate"], previous["conversion_rate"])
    roas_delta = delta_value(current["roas"], previous["roas"])["display"]
    seo_ctr_delta = pp_delta(current["seo_ctr"], previous["seo_ctr"])
    return [
        f"本周 Shopify 收入 {money(current['revenue'])}，订单 {number(current['orders'])}，较上周收入变化 {revenue_delta}；转化率 {pct(current['conversion_rate'])}，较上周 {cvr_delta}。",
        f"Google Ads 本周花费 {money(current['ad_spend'])}，ROAS {current['roas']:.2f}，较上周 {roas_delta}；广告转化价值 {money(current['ad_value'])}。",
        f"GSC 本周曝光 {number(current['seo_impressions'])}、点击 {number(current['seo_clicks'])}，CTR {pct(current['seo_ctr'])}，较上周 {seo_ctr_delta}。",
        "下周优先看三件事：广告预算是否继续压到有效广告组、最高流量落地页是否补齐加购路径、排名 4-20 的 SEO 词是否进入内容更新排期。",
    ]


def build_markdown(data: dict[str, Any]) -> str:
    summary = build_summary(data)
    kpi_md = markdown_table(data["kpis"], [("metric", "指标"), ("current", "本周"), ("previous", "上周"), ("change", "变化")])
    daily_ad_spend_md = markdown_table(data["daily_ad_spend"], [("date", "日期"), ("weekday", "星期"), ("display", "广告消耗")])
    channel_md = markdown_table(data["channels"], [("channel", "渠道"), ("current", "本周 Sessions"), ("previous", "上周 Sessions"), ("change", "变化")])
    ads_md = markdown_table(data["ads"], [("campaign", "广告系列"), ("ad_group", "广告组"), ("cost", "花费"), ("clicks", "点击"), ("conversions", "转化"), ("roas", "ROAS"), ("cpa", "CPA")])
    landing_md = markdown_table(data["weak_landing"], [("page", "落地页"), ("traffic", "流量/点击"), ("ad_cost", "广告花费"), ("add_to_cart_rate", "加购率"), ("orders", "订单")])
    low_ctr_md = markdown_table(data["low_ctr"], [("query", "关键词"), ("impressions", "曝光"), ("clicks", "点击"), ("ctr", "CTR"), ("position", "排名"), ("page", "页面")])
    rank_md = markdown_table(data["rank_opportunities"], [("query", "关键词"), ("impressions", "曝光"), ("clicks", "点击"), ("ctr", "CTR"), ("position", "排名"), ("page", "页面")])
    summary_lines = "\n".join(f"- {line}" for line in summary)
    coverage_lines = "\n".join(
        f"- {source}: {meta['first_date']} 至 {meta['last_date']}；本次对比窗口覆盖 {meta['covered_days_in_comparison_window']} 天。"
        for source, meta in data["source_coverage"]["sources"].items()
    )

    return f"""# 独立站增长周报模板

生成日期：{data['generated_at']}

数据周期：本周 {data['current_start']} 至 {data['current_end']}；上周 {data['previous_start']} 至 {data['previous_end']}

## Executive Summary

{summary_lines}

## 1. 核心 KPI：本周 vs 上周

{kpi_md}

## 2. 每日广告消耗

本周 Google Ads 总花费：{money(data['current']['ad_spend'])}

{daily_ad_spend_md}

## 3. 渠道流量变化

{channel_md}

## 4. Google Ads 本周诊断

{ads_md}

## 5. 高点击低加购落地页

{landing_md}

## 6. SEO 机会：高曝光低 CTR

{low_ctr_md}

## 7. SEO 机会：排名 4-20

{rank_md}

## 8. 下周优先优化事项

1. 复核 Google Ads 高花费广告组：保留 ROAS 较高或有明确转化价值的广告组，降低低 ROAS 且低订单承接的预算。
2. 优化高点击低加购落地页：检查首屏卖点、价格/优惠、产品匹配、移动端加购按钮和结账路径。
3. 推进 SEO 机会词：优先处理排名 4-20 且有曝光的词，同时重写高曝光低 CTR 页面标题与描述。
4. 每周继续跟踪同一张 KPI 表：收入、订单、Sessions、全站转化率、广告 ROAS、SEO CTR 必须固定比较。

## 9. 数据口径与注意事项

- 收入和订单使用 Shopify 真实订单口径；流量使用 GA4 Sessions；转化率 = Shopify 订单 / GA4 Sessions。
- Google Ads 的转化是广告平台转化事件，不一定等同于 Shopify 订单；ROAS 使用广告转化价值 / 广告花费。
- 落地页诊断来自最近 90 天 processed 数据，不代表仅本周页面表现；后续如需要更精确，可把 GA4 落地页事件按周拆分。
- 所有转化率、CTR、加购率均以百分比展示。
- 周报日期按 GA4、Shopify、Google Ads、GSC 四源共同覆盖的最新 7 天对齐；上周对比期也要求四源覆盖。

### 四源覆盖检查

{coverage_lines}
"""


def build_html(data: dict[str, Any]) -> str:
    summary = build_summary(data)
    cards = []
    card_specs = [
        ("Shopify 收入", money(data["current"]["revenue"]), data["kpis"][0]["change"]),
        ("订单数", number(data["current"]["orders"]), data["kpis"][1]["change"]),
        ("全站转化率", pct(data["current"]["conversion_rate"]), data["kpis"][3]["change"]),
        ("Google Ads ROAS", f"{data['current']['roas']:.2f}", data["kpis"][6]["change"]),
    ]
    for label, value, delta in card_specs:
        cards.append(f'<div class="card"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong><em>{html.escape(delta)}</em></div>')

    summary_html = "".join(f"<li>{html.escape(item)}</li>" for item in summary)
    kpi_html = html_table(data["kpis"], [("metric", "指标"), ("current", "本周"), ("previous", "上周"), ("change", "变化")])
    daily_ad_spend_html = "".join(
        '<div class="daily-spend-day">'
        f'<span>{html.escape(row["weekday"])}</span>'
        f'<strong>{html.escape(row["display"])}</strong>'
        f'<em>{html.escape(row["date"])}</em>'
        "</div>"
        for row in data["daily_ad_spend"]
    )
    channel_html = html_table(data["channels"], [("channel", "渠道"), ("current", "本周 Sessions"), ("previous", "上周 Sessions"), ("change", "变化")])
    ads_html = html_table(data["ads"], [("campaign", "广告系列"), ("ad_group", "广告组"), ("cost", "花费"), ("clicks", "点击"), ("conversions", "转化"), ("roas", "ROAS"), ("cpa", "CPA")])
    landing_html = html_table(data["weak_landing"], [("page", "落地页"), ("traffic", "流量/点击"), ("ad_cost", "广告花费"), ("add_to_cart_rate", "加购率"), ("orders", "订单")])
    low_ctr_html = html_table(data["low_ctr"], [("query", "关键词"), ("impressions", "曝光"), ("clicks", "点击"), ("ctr", "CTR"), ("position", "排名"), ("page", "页面")])
    rank_html = html_table(data["rank_opportunities"], [("query", "关键词"), ("impressions", "曝光"), ("clicks", "点击"), ("ctr", "CTR"), ("position", "排名"), ("page", "页面")])
    coverage_html = "".join(
        "<li>"
        f"{html.escape(source)}: {html.escape(meta['first_date'])} 至 {html.escape(meta['last_date'])}；"
        f"本次对比窗口覆盖 {html.escape(str(meta['covered_days_in_comparison_window']))} 天。"
        "</li>"
        for source, meta in data["source_coverage"]["sources"].items()
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>独立站增长周报模板</title>
  <style>
    :root {{
      --ink: #17201a;
      --muted: #657065;
      --line: #d9dfd7;
      --bg: #f7f8f4;
      --panel: #ffffff;
      --green: #287a4d;
      --red: #ad3d38;
      --amber: #8a681b;
      --blue: #245d88;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.58 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 38px 26px 54px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 22px; margin-bottom: 22px; }}
    h1 {{ font-size: clamp(30px, 4vw, 48px); line-height: 1.05; margin: 0 0 12px; letter-spacing: 0; }}
    h2 {{ margin: 30px 0 12px; font-size: 22px; letter-spacing: 0; }}
    h3 {{ margin: 22px 0 10px; font-size: 17px; }}
    p, li {{ color: var(--muted); }}
    .period {{ color: var(--muted); font-size: 14px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 22px 0; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; min-height: 116px; }}
    .card span {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
    .card strong {{ display: block; font-size: 27px; line-height: 1.15; letter-spacing: 0; }}
    .card em {{ display: block; margin-top: 8px; color: var(--blue); font-style: normal; }}
    .ad-spend-strip {{ display: grid; grid-template-columns: 220px 1fr; gap: 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin: -6px 0 20px; }}
    .daily-spend-total {{ border-right: 1px solid var(--line); padding-right: 16px; }}
    .daily-spend-total span, .daily-spend-day span, .daily-spend-day em {{ display: block; color: var(--muted); font-size: 13px; font-style: normal; }}
    .daily-spend-total strong {{ display: block; margin-top: 8px; font-size: 28px; line-height: 1.15; }}
    .daily-spend-days {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }}
    .daily-spend-day {{ background: #f7f8f4; border: 1px solid var(--line); border-radius: 8px; padding: 10px; min-height: 82px; }}
    .daily-spend-day strong {{ display: block; margin: 4px 0 2px; font-size: 16px; line-height: 1.2; }}
    section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 20px; margin: 16px 0; }}
    .summary {{ margin: 0; padding-left: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ color: #39443b; background: #eef2eb; font-weight: 650; }}
    .up {{ color: var(--green); font-weight: 650; }}
    .down {{ color: var(--red); font-weight: 650; }}
    .flat {{ color: var(--amber); font-weight: 650; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .next ol {{ margin-bottom: 0; }}
    .note {{ color: var(--muted); font-size: 13px; }}
    @media (max-width: 860px) {{
      main {{ padding: 24px 14px 42px; }}
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .ad-spend-strip {{ grid-template-columns: 1fr; }}
      .daily-spend-total {{ border-right: 0; border-bottom: 1px solid var(--line); padding: 0 0 12px; }}
      .daily-spend-days {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      section {{ padding: 14px; overflow-x: auto; }}
      table {{ min-width: 720px; }}
    }}
    @media (max-width: 520px) {{
      .cards {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>独立站增长周报模板</h1>
      <div class="period">生成日期：{html.escape(data['generated_at'])} · 本周 {html.escape(data['current_start'])} 至 {html.escape(data['current_end'])} · 对比上周 {html.escape(data['previous_start'])} 至 {html.escape(data['previous_end'])}</div>
    </header>

    <section>
      <h2>Executive Summary</h2>
      <ul class="summary">{summary_html}</ul>
    </section>

    <div class="cards">{''.join(cards)}</div>

    <div class="ad-spend-strip">
      <div class="daily-spend-total">
        <span>本周 Google Ads 总花费</span>
        <strong>{html.escape(money(data['current']['ad_spend']))}</strong>
      </div>
      <div class="daily-spend-days">{daily_ad_spend_html}</div>
    </div>

    <section>
      <h2>核心 KPI：本周 vs 上周</h2>
      <p>先看经营结果，再看流量和广告效率。转化率统一用百分比，变化用百分点展示。</p>
      {kpi_html}
    </section>

    <section>
      <h2>渠道流量变化</h2>
      <p>这张表用 GA4 Sessions 判断流量结构是否变化，帮助判断问题来自流量减少还是转化承接变弱。</p>
      {channel_html}
    </section>

    <section>
      <h2>Google Ads 本周诊断</h2>
      <p>按本周广告组花费排序，优先排查高花费但 ROAS 或订单承接偏弱的对象。</p>
      {ads_html}
    </section>

    <section>
      <h2>高点击低加购落地页</h2>
      <p>这部分来自 90 天落地页诊断，用来做下周页面优化清单；后续可继续拆成周维度。</p>
      {landing_html}
    </section>

    <section>
      <h2>SEO 机会：高曝光低 CTR</h2>
      <p>这些词已有搜索曝光，但点击率偏低，优先检查标题、描述、首屏承诺和页面匹配度。</p>
      {low_ctr_html}
    </section>

    <section>
      <h2>SEO 机会：排名 4-20</h2>
      <p>这些词离首页或高位还有推进空间，适合做内容补强、内链和 FAQ 更新。</p>
      {rank_html}
    </section>

    <section class="next">
      <h2>下周优先优化事项</h2>
      <ol>
        <li>复核 Google Ads 高花费广告组：保留 ROAS 较高或有明确转化价值的广告组，降低低 ROAS 且低订单承接的预算。</li>
        <li>优化高点击低加购落地页：检查首屏卖点、价格/优惠、产品匹配、移动端加购按钮和结账路径。</li>
        <li>推进 SEO 机会词：优先处理排名 4-20 且有曝光的词，同时重写高曝光低 CTR 页面标题与描述。</li>
        <li>每周继续跟踪同一张 KPI 表：收入、订单、Sessions、全站转化率、广告 ROAS、SEO CTR 必须固定比较。</li>
      </ol>
    </section>

    <section>
      <h2>口径说明</h2>
      <p class="note">收入和订单使用 Shopify 真实订单口径；流量使用 GA4 Sessions；转化率 = Shopify 订单 / GA4 Sessions。Google Ads 的转化是广告平台转化事件，不一定等同于 Shopify 订单。所有转化率、CTR、加购率均以百分比展示。周报日期按 GA4、Shopify、Google Ads、GSC 四源共同覆盖的最新 7 天对齐；上周对比期也要求四源覆盖。</p>
      <h3>四源覆盖检查</h3>
      <ul class="note">{coverage_html}</ul>
    </section>
  </main>
</body>
</html>
"""


def write_outputs(data: dict[str, Any], markdown_path: Path, html_path: Path, json_path: Path) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    markdown_path.write_text(build_markdown(data), encoding="utf-8")
    html_path.write_text(build_html(data), encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("Weekly markdown written: %s", markdown_path)
    LOGGER.info("Weekly HTML written: %s", html_path)
    LOGGER.info("Weekly summary JSON written: %s", json_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a weekly growth report template with week-over-week comparison.")
    parser.add_argument("--markdown-out", default=str(OUTPUTS_DIR / "weekly_growth_report_template.md"))
    parser.add_argument("--html-out", default=str(OUTPUTS_DIR / "weekly_growth_report_template.html"))
    parser.add_argument("--json-out", default=str(OUTPUTS_DIR / "weekly_growth_report_template.json"))
    args = parser.parse_args()

    data = build_report_data()
    write_outputs(data, Path(args.markdown_out), Path(args.html_out), Path(args.json_out))


if __name__ == "__main__":
    main()
