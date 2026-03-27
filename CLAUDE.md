# CLAUDE.md — Meichen Product Scout

> 本文件是 Claude Code 的项目上下文文档。每次新会话自动读取，无需重复说明背景。

---

## 项目概览

**项目名**：Meichen Product Scout（美晨跨境选品系统）
**目标**：自动化选品 pipeline，每日抓取 AliExpress 进价 + Amazon.de/eBay.de 售价，计算利润率 ≥30% 的商品，写入 Google Sheets 供团队决策。
**GitHub**：`github.com/wyl2607/meichen`（main 分支，公开）
**VPS**：RackNerd VPS，通过 Tailscale 接入，hostname `racknerd-32738e2.tail27b5c.ts.net`，IP `100.125.28.79`

---

## 目录结构

```
product-scout/
├── CLAUDE.md              ← 本文件（Claude Code 上下文）
├── REQUIREMENTS.md        ← 功能需求文档（F1-F8）
├── PROGRESS.md            ← Sprint 执行 Timeline（所有修复记录）
├── README.md              ← GitHub 公司主页（对外展示）
├── config.py              ← 所有配置项，从 .env 加载
├── models.py              ← Product dataclass
├── requirements.txt       ← Python 依赖
├── .env                   ← 🔴 敏感！API Keys，不入 Git
├── .env.example           ← 配置模板（可公开）
├── credentials.json       ← 🔴 敏感！Google Service Account，不入 Git
├── scrapers/
│   ├── aliexpress.py      ← ScraperAPI + BS4，返回 EUR 价格
│   ├── amazon_de.py       ← requests + BS4，直接抓 Amazon.de
│   └── ebay_de.py         ← eBay Finding API v1
├── processors/
│   ├── cleaner.py         ← 去重 + 过滤无价格记录
│   └── profit_calculator.py ← FBA/eBay 费率 → 净利润率
├── storage/
│   └── sheets_writer.py   ← gspread 写入 Google Sheets
├── scheduler/
│   └── main.py            ← 入口，24h 定时 pipeline
└── data/raw/              ← 🟡 快照 JSON，不入 Git
    └── snapshot_YYYYMMDD_HHMMSS.json
```

---

## 快速开始

```bash
# 1. 安装依赖（Python 3.11+）
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入真实 API Key

# 3. 运行一次 pipeline（立即执行）
python scheduler/main.py

# 4. 后台持续运行（每 24h 自动执行）
nohup python scheduler/main.py > logs/pipeline.log 2>&1 &
```

---

## 关键配置（.env）

| 变量 | 状态 | 说明 |
|------|------|------|
| `SCRAPER_API_KEY` | ✅ 已配置 | AliExpress 反爬代理，EU 节点 |
| `GOOGLE_SHEETS_CREDS_FILE` | ✅ 已配置 | Google Service Account JSON |
| `GOOGLE_SHEET_ID` | ✅ 已配置 | 目标 Sheet |
| `CNY_TO_EUR` | ✅ 已配置 | 汇率，建议每月更新 |
| `EBAY_APP_ID` | ❌ 待填 | eBay Developer App ID |
| `AMAZON_ACCESS_KEY` | ❌ 待填 | Amazon PA-API（申请中）|

**Google Sheets API 启用**（用户操作）：
- Sheets: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1098098407491
- Drive: https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1098098407491

---

## 架构要点（避免踩坑）

### AliExpress 价格单位
ScraperAPI 走 EU 节点，AliExpress 返回 **EUR**（不是 CNY）。
代码中 `source_price_eur` 直接用，`source_price_cny = eur / CNY_TO_EUR` 反推。

### CSS 选择器脆弱性
AliExpress 频繁改版，选择器可能随时失效。当前有效选择器（2026-03-27 验证）：
- 容器：`.search-item-card-wrapper-gallery`
- 价格：`.lw_kt`
- 标题：`h3`

如果 AliExpress 返回 0 条，第一步是跑诊断脚本探测实际 HTML class。

### Amazon.de 选择器（2026-03-27 验证）
- 标题：`h2 span`（不是 `h2 a span`，anchor 嵌套改了）
- URL：从 `data-asin` 构建 `/dp/{asin}`（比 href 更稳定）
- 价格：`.a-price-whole` + `.a-price-fraction`

### eBay 未配置时
`EBAY_APP_ID=placeholder` → eBay API 返回 HTTP 500。
已处理：`scrape_keyword()` 捕获 `HTTPError`，返回空迭代器，pipeline 继续。

### Google Sheets 未启用时
写入失败会 `log.warning()` 但不崩溃。Pipeline 仍正常保存 JSON 快照。

---

## 利润计算公式

```python
# processors/profit_calculator.py
amazon_net = amazon_price * (1 - FBA_FEE_RATE) - shipping - source_price_eur
ebay_net   = ebay_price   * (1 - EBAY_FEE_RATE) - shipping - source_price_eur
profit_margin = max(net_profits) / max(sell_prices)
# 阈值：MIN_PROFIT_MARGIN = 0.30 (30%)
```

---

## 上次 Pipeline 跑通结果（2026-03-27）

| 指标 | 值 |
|------|-----|
| AliExpress 商品 | 92 条 |
| Amazon.de 商品 | 500 条 |
| 去重过滤后 | 482 条 |
| 利润率 ≥30% | 158 条 |
| 快照路径 | `data/raw/snapshot_20260327_104801.json` |
| Top 品类 | LED Streifen（均利润率 59.3%）|
| Top 商品 | LED Streifen，进价 €1.05，售价 €89.99，利润率 **79.9%** |

---

## 部署：VPS（RackNerd via Tailscale）

**VPS 信息**：
- Tailscale hostname：`racknerd-32738e2.tail27b5c.ts.net`
- IPv4（Tailscale）：`100.125.28.79`
- IPv6（Tailscale）：`fd7a:115c:a1e0::8a33:1c4f`

**部署策略（安全优先）**：
1. 代码：VPS 从 GitHub `git clone/pull`（无敏感信息）
2. 密钥：本地通过 `rsync` 经 Tailscale 加密隧道推送 `.env` + `credentials.json`
3. 定时任务：VPS 上用 `systemd` service 或 `cron` 运行 `scheduler/main.py`

**部署脚本**（本地执行）：
```bash
# 推送密钥到 VPS（Tailscale 加密，安全）
rsync -avz .env credentials.json root@100.125.28.79:/opt/meichen/

# 代码从 GitHub 部署
ssh root@100.125.28.79 "
  cd /opt/meichen && git pull origin main
  pip3 install -r requirements.txt
"
```

---

## 云备份策略

| 类型 | 方案 | 说明 |
|------|------|------|
| 代码 | GitHub `wyl2607/meichen`（public） | 无敏感信息，公开没问题 |
| 密钥 | VPS 本地存储（Tailscale 加密传输） | 不上云，最安全 |
| 数据快照 | VPS `/opt/meichen/data/raw/` | 本地保存，定期手动导出 |
| 备用密钥 | 加密后放私有 GitHub Gist | 用 `gpg --symmetric` 加密后可上传 |

---

## Git 提交规范

```
feat:  新功能
fix:   Bug 修复
docs:  文档更新（REQUIREMENTS.md / PROGRESS.md / CLAUDE.md）
refactor: 重构
chore: 杂项（依赖更新、配置调整）
```

**敏感文件检查**（每次 commit 前）：
- `.env` 在 `.gitignore` ✅
- `credentials.json` 在 `.gitignore` ✅
- `data/raw/*.json` 在 `.gitignore` ✅

---

## 待办（Next Actions）

| 优先级 | 事项 | 操作人 |
|--------|------|--------|
| 🔴 高 | 启用 Google Sheets API + Drive API | 用户（GCP Console）|
| 🔴 高 | VPS 部署运行 | Claude + 用户 |
| 🟡 中 | 配置 eBay App ID | 用户（developer.ebay.com）|
| 🟡 中 | 删除 GitHub master 分支 | 用户（GitHub Settings）|
| 🟢 低 | 接入 Amazon PA-API 5.0 | Claude |
| 🟢 低 | 定期检查 AliExpress 选择器 | Claude（每月）|
