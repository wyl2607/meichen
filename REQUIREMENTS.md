# Meichen Product Scout — 需求文档

**项目**：Meichen 跨境选品分析系统
**版本**：v1.0
**更新**：2026-03-27

---

## 一、业务背景

Meichen（美晨）是一家跨境电商公司，核心业务是将中国优质商品引入德国/欧洲市场，通过 Amazon.de 和 eBay.de 销售。

**核心痛点**：人工选品效率低，无法快速识别高利润差价商品。

**解决方案**：自动化选品 pipeline，每日抓取 AliExpress 进价 + Amazon.de/eBay.de 售价，计算利润率，筛选高价值商品并写入 Google Sheets 供团队决策。

---

## 二、功能需求

### F1 — AliExpress 进价抓取
- **目标**：获取中国供货价（EUR，通过 ScraperAPI EU 节点）
- **输入**：德语搜索关键词列表（config.py 中配置）
- **输出**：`Product` 对象，含 `source_price_eur`、`source_price_cny`、标题、图片、链接
- **技术**：requests + BeautifulSoup + ScraperAPI 代理
- **上限**：每关键词最多 `MAX_RESULTS_PER_KEYWORD`（默认 50）条
- **状态**：✅ 已实现并验证

### F2 — Amazon.de 售价抓取
- **目标**：获取德国亚马逊上同类商品的市场售价
- **输入**：关键词 + AliExpress 平均进价（作为基准参考）
- **输出**：`Product` 对象，含 `amazon_price_eur`、ASIN、标题、链接
- **技术**：requests + BeautifulSoup，直接请求（带 DE 语言 Header）
- **状态**：✅ 已实现并验证（每关键词稳定返回 50 条）

### F3 — eBay.de 售价抓取
- **目标**：通过 eBay Finding API 获取德国 eBay 固定价商品售价
- **输入**：关键词
- **输出**：`Product` 对象，含 `ebay_price_eur`
- **技术**：eBay Finding API v1（需 `EBAY_APP_ID`）
- **状态**：⚠️ 待配置（需在 `.env` 填入真实 `EBAY_APP_ID`）
- **依赖**：申请地址 https://developer.ebay.com

### F4 — 利润计算
- **公式**：
  ```
  Amazon净利 = amazon_price × (1 - FBA_FEE_RATE) - 运费 - 进价
  eBay净利   = ebay_price   × (1 - EBAY_FEE_RATE) - 运费 - 进价
  利润率      = max(净利) / max(售价)
  ```
- **阈值**：`MIN_PROFIT_MARGIN = 0.30`（30%）
- **状态**：✅ 已实现并验证

### F5 — 数据去重与过滤
- 去重策略：标准化标题后取利润数据更完整的记录
- 过滤条件：amazon_price 和 ebay_price 均为 None 的记录丢弃
- **状态**：✅ 已实现

### F6 — Google Sheets 写入
- **目标**：将利润率 ≥30% 的商品追加写入指定 Google Sheet
- **表头**：product_id / title / source_platform / source_price_cny / source_price_eur / amazon_price_eur / ebay_price_eur / estimated_shipping_eur / profit_margin / search_keyword / scraped_at / image_url / product_url
- **技术**：gspread + Google Service Account
- **状态**：⚠️ 待启用 API（需在 Google Cloud Console 启用 Sheets API + Drive API）
- **项目 ID**：`1098098407491`
- **启用链接**：
  - Sheets: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1098098407491
  - Drive: https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1098098407491

### F7 — 定时调度
- 每 24 小时自动执行一次完整 pipeline
- 启动时立即执行一次
- **状态**：✅ 已实现（`scheduler/main.py`）

### F8 — 原始数据快照
- 每次运行后将全量数据保存为 `data/raw/snapshot_YYYYMMDD_HHMMSS.json`
- 供复盘/回溯使用
- **状态**：✅ 已实现

---

## 三、非功能需求

| 维度 | 要求 |
|------|------|
| 请求间隔 | ≥ 2 秒（`REQUEST_DELAY_SECONDS`），避免封禁 |
| 最大抓取量 | 每关键词 50 条（`MAX_RESULTS_PER_KEYWORD`） |
| 安全 | API Key 仅存 `.env`，不入 Git |
| 容错 | 单个 scraper 失败不中断整个 pipeline |
| 编码 | Python 3.11+，类型注解，dataclass |

---

## 四、配置项（.env）

| 变量名 | 说明 | 状态 |
|--------|------|------|
| `CNY_TO_EUR` | 人民币/欧元汇率，每日更新 | ✅ 已配置 |
| `SCRAPER_API_KEY` | ScraperAPI 密钥（用于 AliExpress） | ✅ 已配置 |
| `GOOGLE_SHEETS_CREDS_FILE` | Service Account JSON 文件路径 | ✅ 已配置 |
| `GOOGLE_SHEET_ID` | 目标 Google Sheet ID | ✅ 已配置 |
| `EBAY_APP_ID` | eBay Developer App ID | ❌ 待填入 |
| `EBAY_CERT_ID` | eBay Developer Cert ID | ❌ 待填入 |
| `AMAZON_ACCESS_KEY` | Amazon PA-API 5.0 Access Key | ❌ 待填入（PA-API 申请中）|
| `AMAZON_SECRET_KEY` | Amazon PA-API 5.0 Secret Key | ❌ 待填入 |
| `AMAZON_PARTNER_TAG` | Amazon Associates Tag（格式：xxx-21） | ❌ 待填入 |

---

## 五、关键词配置（config.py）

当前搜索关键词（10 个德语品类）：

```
LED Streifen / Handyhülle iPhone / Fitnessband / Küchen Gadget /
Haustier Zubehör / Bluetooth Kopfhörer / USB Hub / Garten Werkzeug /
Baby Spielzeug / Yoga Matte
```

---

## 六、已知限制

1. **AliExpress CSS 选择器脆弱**：AliExpress 频繁改版，选择器需定期维护（最近一次更新：2026-03-27）
2. **Amazon.de 无代理**：直接请求存在被限速/CAPTCHA 风险，长期建议接入 PA-API 5.0 替代爬取
3. **eBay 数据缺失**：API 未配置导致 eBay 价格为空，影响部分品类利润计算准确性
4. **利润率偏高风险**：进价来自 AliExpress 最低价，实际采购需验证 MOQ / 货运成本
