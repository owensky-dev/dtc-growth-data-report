# DTC 独立站增长数据报告 Skill

[English README](README.md)

这是一个 Codex skill，用来搭建可复用的独立站增长数据报告系统，统一连接 GA4、Google Search Console、Google Ads 和 Shopify 数据。

它适合用于：

- 为 DTC 独立站搭建本地数据诊断系统。
- 自动生成老板版每周增长周报。
- 分析渠道流量、广告效率、落地页转化、SEO 机会和 Shopify 真实收入订单。
- 将一套已跑通的数据报告流程复用到新品牌、新站点或新项目。

## 包含能力

- GA4 数据拉取：渠道表现、落地页表现、加购/转化事件。
- GSC 数据拉取：搜索词、页面、点击、曝光、CTR、平均排名。
- Google Ads 数据拉取：广告系列、广告组、搜索词、落地页、花费、点击、转化、转化价值。
- Shopify 数据拉取：订单、收入、税费、订单状态、来源信息，并输出包含 0 订单日的每日销售表。
- 数据统一转换：输出标准 processed CSV。
- 周报模板：自动生成“本周 vs 上周”的老板版 HTML 和 Markdown 周报。
- 操盘手增强周报：包含经营判断、收入归因、漏斗健康、广告预算动作、页面优化动作、SEO 意图分组、异常提醒、下周行动清单和数据健康检查。
- 独立站增长诊断看板：输出老板可读的本地 HTML dashboard。
- 配置参考、数据字段说明和报告工作流说明。

## 安装

把 skill 文件夹复制到 Codex skills 目录：

```bash
cp -R dtc-growth-data-report ~/.codex/skills/
```

复制后，重启 Codex 或开启新的 Codex 会话，让 skill 被自动发现。

## 使用方式

示例：

```text
使用 $dtc-growth-data-report 帮我连接 GA4、GSC、Google Ads 和 Shopify 数据，并生成本周增长周报。
```

如果是在新项目中安装完整管线，可以这样说：

```text
使用 $dtc-growth-data-report 在这个项目里安装独立站增长数据报告系统，并生成老板版周报。
```

## 必要配置

在项目中根据 `.env.example` 创建 `.env`，然后填写本地密钥。不同数据源需要的配置如下：

### GA4

- `GOOGLE_APPLICATION_CREDENTIALS`：Google service account JSON 文件绝对路径。
- `GA4_PROPERTY_ID`：GA4 property ID。

### Google Search Console

- `GOOGLE_APPLICATION_CREDENTIALS`：可复用同一个 service account。
- `GSC_SITE_URL`：Search Console 站点属性 URL。

### Google Ads

- `GOOGLE_ADS_CUSTOMER_ID`
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID`

也可以使用：

- `GOOGLE_ADS_CONFIGURATION_FILE_PATH`

### Shopify

- `SHOPIFY_SHOP_DOMAIN`
- `SHOPIFY_ADMIN_ACCESS_TOKEN`
- `SHOPIFY_API_VERSION`

## 默认输出

安装并运行管线后，默认生成：

- `data/raw/`：GA4、GSC、Google Ads、Shopify 原始 CSV。
- `data/raw/shopify_sales_by_day_90d.csv`：Shopify 每日订单和收入，包含 0 订单日，用于判断数据覆盖是否完整。
- `data/processed/channel_performance.csv`
- `data/processed/landing_page_performance.csv`
- `data/processed/google_ads_diagnosis.csv`
- `data/processed/search_query_opportunities.csv`
- `reports/weekly_growth_diagnosis.md`
- `outputs/weekly_growth_report_template.html`
- `outputs/weekly_growth_report_template.md`
- `outputs/weekly_growth_report_template.json`

## 报告口径

- 收入和订单默认以 Shopify 为准。
- 流量、落地页行为、站内事件默认以 GA4 为准。
- 广告花费、点击、广告转化、转化价值、ROAS、CPA 默认以 Google Ads 为准。
- SEO 点击、曝光、CTR、平均排名默认以 GSC 为准。
- 全站转化率 = Shopify 订单数 / GA4 Sessions。
- 周报默认比较四个核心数据源共同覆盖的最近完整 7 天与再往前 7 天。
- 如果某个数据源延迟，周报会整体回退到 GA4、Shopify、Google Ads、GSC 都有数据的最新 7 天；如果找不到四源对齐窗口，则停止生成并报告缺口。
- 周报不只输出指标表，还会把结果整理成操盘动作：预算怎么调、页面怎么改、SEO 先做哪类词、下周谁负责什么。
- 转化率、CTR、加购率等比例指标统一用百分比展示。

## 安全注意事项

不要提交或分享：

- `.env`
- Google service account JSON
- OAuth client secret 文件
- Google Ads refresh token
- Shopify Admin API token
- 任何真实密钥、账号密钥或私钥

本仓库只包含 `.env.example`，不包含真实密钥。

## 推荐 GitHub 标签

`codex-skill`, `dtc`, `ecommerce`, `shopify`, `ga4`, `google-search-console`, `google-ads`, `growth-analytics`, `marketing-analytics`, `weekly-report`
