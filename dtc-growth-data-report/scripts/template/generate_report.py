from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from config import DATA_PROCESSED_DIR, REPORTS_DIR, ensure_dirs, setup_logging


LOGGER = setup_logging("generate_report")


def read_processed(filename: str) -> pd.DataFrame:
    path = DATA_PROCESSED_DIR / filename
    if not path.exists():
        LOGGER.warning("Missing processed file: %s", path)
        return pd.DataFrame()
    frame = pd.read_csv(path)
    LOGGER.info("Loaded %s rows=%s", filename, len(frame))
    return frame


def money(value: float) -> str:
    return f"${value:,.2f}"


def number(value: float) -> str:
    return f"{value:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def metric(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def table(frame: pd.DataFrame, columns: list[str], limit: int = 10) -> str:
    if frame.empty:
        return "_暂无数据_"
    available = [column for column in columns if column in frame.columns]
    if not available:
        return "_暂无可展示字段_"
    view = frame[available].head(limit).copy()
    return view.to_markdown(index=False)


def section_missing(frames: dict[str, pd.DataFrame]) -> str:
    missing = [name for name, frame in frames.items() if frame.empty]
    if not missing:
        return "四类 processed 数据均已生成并可读取。"
    return "以下数据为空或尚未生成：" + "、".join(missing) + "。报告会先基于已有数据输出。"


def build_priorities(
    ads_risks: pd.DataFrame,
    weak_landing: pd.DataFrame,
    low_ctr: pd.DataFrame,
    rank_4_20: pd.DataFrame,
    seo_for_ads: pd.DataFrame,
    ads_for_seo: pd.DataFrame,
) -> list[str]:
    priorities: list[str] = []
    if not ads_risks.empty:
        priorities.append("先暂停或下调高花费低转化广告组，逐个检查搜索词、落地页匹配度和转化追踪。")
    if not weak_landing.empty:
        priorities.append("优先优化高点击低加购落地页，检查首屏承诺、价格/促销露出、产品匹配和移动端加购路径。")
    if not low_ctr.empty:
        priorities.append("重写高曝光低 CTR SEO 关键词对应页面的标题、描述和首屏信息，提高搜索结果点击率。")
    if not rank_4_20.empty:
        priorities.append("把排名 4-20 的机会词拆成页面级优化清单，补充内链、FAQ、评测/对比内容和结构化数据。")
    if not seo_for_ads.empty:
        priorities.append("从已有自然搜索机会词中挑选高意图词做小预算 Search 测试，验证广告转化潜力。")
    if not ads_for_seo.empty:
        priorities.append("把已在广告侧跑出转化或高 ROAS 的搜索词转成 SEO 内容选题，沉淀长期免费流量。")
    if not priorities:
        priorities.append("先完成四个数据源的 90 天原始数据拉取，再做下一轮诊断排序。")
    return priorities[:8]


def generate_report(out: Path) -> None:
    channel = read_processed("channel_performance.csv")
    landing = read_processed("landing_page_performance.csv")
    ads = read_processed("google_ads_diagnosis.csv")
    queries = read_processed("search_query_opportunities.csv")
    frames = {
        "channel_performance.csv": channel,
        "landing_page_performance.csv": landing,
        "google_ads_diagnosis.csv": ads,
        "search_query_opportunities.csv": queries,
    }

    shopify_rows = channel[channel["source"] == "Shopify"] if not channel.empty and "source" in channel.columns else pd.DataFrame()
    ga4_rows = channel[channel["source"] == "GA4"] if not channel.empty and "source" in channel.columns else channel
    overall_revenue = metric(shopify_rows, "revenue") if not shopify_rows.empty else metric(ga4_rows, "revenue")
    overall_orders = metric(shopify_rows, "orders") if not shopify_rows.empty else metric(ga4_rows, "orders")
    traffic = metric(channel, "sessions")
    conversion_rate = overall_orders / traffic if traffic else 0

    google_ads = channel[channel["source"] == "Google Ads"] if not channel.empty and "source" in channel.columns else pd.DataFrame()
    ad_spend = metric(google_ads, "cost")
    ad_conversions = metric(google_ads, "conversions")
    ad_revenue = metric(google_ads, "revenue")
    roas = ad_revenue / ad_spend if ad_spend else 0
    cpa = ad_spend / ad_conversions if ad_conversions else 0

    ads_risks = ads[ads.get("diagnosis", "") == "high_spend_low_conversion"] if not ads.empty else pd.DataFrame()
    weak_landing = landing[landing.get("diagnosis", "") == "high_click_low_add_to_cart"] if not landing.empty else pd.DataFrame()
    low_ctr = queries[queries.get("opportunity_type", "") == "high_impression_low_ctr"] if not queries.empty else pd.DataFrame()
    rank_4_20 = queries[queries.get("opportunity_type", "") == "rank_4_20"] if not queries.empty else pd.DataFrame()
    seo_for_ads = queries[queries.get("opportunity_type", "") == "seo_keyword_for_ads"] if not queries.empty else pd.DataFrame()
    ads_for_seo = queries[queries.get("opportunity_type", "") == "ads_keyword_for_seo"] if not queries.empty else pd.DataFrame()

    priorities = build_priorities(ads_risks, weak_landing, low_ctr, rank_4_20, seo_for_ads, ads_for_seo)
    priority_lines = "\n".join(f"{index}. {item}" for index, item in enumerate(priorities, start=1))

    content = f"""# 独立站每周增长诊断

生成日期：{date.today().isoformat()}

## 数据状态

{section_missing(frames)}

## 总体表现

- 总收入：{money(overall_revenue)}
- 订单数：{number(overall_orders)}
- 流量 Sessions：{number(traffic)}
- 转化率：{pct(conversion_rate)}

## Google Ads 表现

- 花费：{money(ad_spend)}
- 转化：{number(ad_conversions)}
- 转化价值：{money(ad_revenue)}
- ROAS：{roas:.2f}
- CPA：{money(cpa)}

## 渠道表现

{table(channel, ["source", "channel", "sessions", "clicks", "cost", "orders", "revenue", "conversion_rate", "roas", "cpa"], 20)}

## 高花费低转化广告系列

{table(ads_risks, ["campaign_name", "ad_group_name", "cost", "clicks", "conversions", "conversion_value", "roas", "cpa", "diagnosis"], 10)}

## 高点击低加购落地页

{table(weak_landing, ["landing_page_url", "sessions", "ad_clicks", "ad_cost", "add_to_cart", "add_to_cart_rate", "orders", "revenue", "diagnosis"], 10)}

## 高曝光低 CTR SEO 关键词

{table(low_ctr, ["query", "page", "impressions", "clicks", "ctr", "position", "opportunity_type"], 15)}

## 排名 4-20 的 SEO 机会词

{table(rank_4_20, ["query", "page", "impressions", "clicks", "ctr", "position", "opportunity_type"], 15)}

## 值得新增广告投放的 SEO 关键词

{table(seo_for_ads, ["query", "page", "impressions", "clicks", "ctr", "position", "paid_coverage", "opportunity_type"], 15)}

## 值得新增 SEO 内容的广告关键词

{table(ads_for_seo, ["query", "impressions", "clicks", "cost", "conversions", "conversion_value", "opportunity_type"], 15)}

## 下周优先优化事项

{priority_lines}

## 口径说明

- 原始数据统一读取 `data/raw/`，processed 数据统一输出到 `data/processed/`。
- Google Ads 花费来自 `metrics.cost_micros / 1,000,000`。
- 高花费低转化默认定义：广告组花费不低于 50 或不低于中位数，且转化小于 1。
- 高点击低加购默认定义：落地页广告点击或 GA4 sessions 不低于 100，且加购率低于 2%。
- SEO 机会词默认来自 GSC：高曝光低 CTR 为 impressions >= 500 且 CTR < 2%；排名机会词为平均排名 4-20。
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    LOGGER.info("Report written: %s", out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly growth diagnosis markdown report.")
    parser.add_argument("--out", default=str(REPORTS_DIR / "weekly_growth_diagnosis.md"))
    args = parser.parse_args()

    ensure_dirs()
    generate_report(Path(args.out))


if __name__ == "__main__":
    main()
