# Meichen Product Scout — 任务执行 Timeline

**项目**：Meichen 跨境选品分析系统
**记录人**：Claude (AI Engineering Partner)
**最后更新**：2026-03-27

---

## Sprint 1 — 项目初始化与基础架构

### [2026-03-26] 项目创建

**目标**：从零搭建跨境选品 pipeline

**完成内容**：
- 初始化项目目录结构：`scrapers/` / `processors/` / `storage/` / `scheduler/`
- 创建核心模型 `models.py`：`Product` dataclass，含 source/sell 双价格字段
- 实现 `config.py`：从 `.env` 加载所有配置，含汇率、利润阈值、API Key
- 实现 `scrapers/aliexpress.py`：ScraperAPI 代理抓取 AliExpress 进价
- 实现 `scrapers/amazon_de.py`：requests + BeautifulSoup 抓取 Amazon.de 售价
- 实现 `scrapers/ebay_de.py`：eBay Finding API 抓取 eBay.de 售价
- 实现 `processors/profit_calculator.py`：FBA/eBay 费率扣除后净利润率计算
- 实现 `processors/cleaner.py`：基于标准化标题的去重 + 无价格记录过滤
- 实现 `storage/sheets_writer.py`：gspread 写入 Google Sheets
- 实现 `scheduler/main.py`：每 24 小时定时执行完整 pipeline
- 创建 `.env.example`、`.gitignore`、`requirements.txt`

**问题记录**：
- `ModuleNotFoundError: No module named 'config'`：`scheduler/main.py` 在子目录运行时找不到项目根。
  **修复**：`scheduler/main.py` 第 14 行加入 `sys.path.insert(0, os.path.dirname(os.path.dirname(...)))`

---

### [2026-03-26] GitHub 仓库与公司定位

**目标**：将 GitHub 仓库作为申请 Amazon PA-API 5.0 的"公司网站"使用

**完成内容**：
- 创建 GitHub 仓库：`github.com/wyl2607/meichen`
- 将 README.md 从技术工具文档**重写为公司主页**（Meichen / 美晨，跨境电商公司定位）
- 内容含：使命宣言、What We Do、Why Meichen 对比表、Technology 章节（PA-API 5.0 业务背景）、Markets & Presence、联系方式
- 将所有历史 commit squash 为单一干净提交：`feat: launch Meichen cross-border e-commerce platform`（18 files, 769 insertions）
- Force push 到 `main` 分支，消除历史 diff 泄露

**问题记录**：
- `git push origin --delete master` 失败：`master` 是 GitHub 默认分支，无法直接删除。
  **解决方案**：需先在 GitHub Settings > Branches 将默认分支切换至 `main`，再删除 `master`

---

## Sprint 2 — Scraper 修复与 Pipeline 跑通

### [2026-03-27] Git 状态修复

**问题**：
1. 本地存在未完成的 `git rebase`（`.git/rebase-merge/` 目录残留）
2. 本地 `main` 比 `origin/main` 多 2 个旧 commit（与上次 force push 不一致）

**修复步骤**：
```bash
git rebase --abort          # 中止卡住的 rebase
git reset --hard origin/main  # 本地对齐远端单一干净 commit
```
**结果**：`HEAD is now at dd86579 feat: launch Meichen cross-border e-commerce platform`

---

### [2026-03-27] AliExpress 选择器更新

**问题**：`scrapers/aliexpress.py` 返回 0 条数据
**根因**：AliExpress 重构了前端，旧 CSS class（如 `.list--gallery--34TropR`）已失效

**诊断过程**：
1. 通过 ScraperAPI 拉取真实 HTML，确认页面有效返回（642KB 内容）
2. 探测真实容器 class：发现 `.search-item-card-wrapper-gallery`（25 个元素）
3. 遍历第一个商品卡片所有 DOM 节点，定位价格节点 `.lw_kt`（当前/折扣价）
4. 确认 title 在 `h3`，链接在 `a.search-card-item`

**关键发现**：ScraperAPI 走 EU 节点，AliExpress 返回的价格单位已是 **EUR**（非 CNY）
→ 更新逻辑：直接用 EUR 价格作为 `source_price_eur`，反推 `source_price_cny = eur / CNY_TO_EUR`

**修复文件**：`scrapers/aliexpress.py`
- 容器选择器：`.list--gallery--34TropR .item--wrap--2dh0oCq` → `.search-item-card-wrapper-gallery`
- 价格选择器：`.price--currentPriceText--V8_y_b5` → `.lw_kt`
- 新增异常捕获：`requests.exceptions.RequestException` → 记录 warning 不崩溃

**验证结果**：✅ 每关键词稳定返回 10-12 条，价格 EUR 字段正常

---

### [2026-03-27] Amazon.de 选择器修复

**问题**：`scrapers/amazon_de.py` 返回 0 条数据，title 为 None
**根因**：`h2 a span` 在新版 Amazon HTML 中 `<a>` 标签的嵌套层级变了

**诊断过程**：
1. 直接请求 Amazon.de，确认 200 状态 + 48 条 `[data-component-type="s-search-result"]`（选择器本身没问题）
2. 逐一测试候选 title 选择器，定位有效选择器为 `h2 span`
3. 确认 price 选择器 `.a-price-whole` + `.a-price-fraction` 仍有效
4. 发现 `h2 a` href 为 None → 改用 ASIN 构建 URL：`/dp/{asin}`

**修复文件**：`scrapers/amazon_de.py`
- Title：`h2 a span` → `h2 span`
- URL：`h2 a["href"]` → `AMAZON_DE_BASE_URL + "/dp/" + card.get("data-asin")`（更稳定）

**验证结果**：✅ 每关键词稳定返回 50 条，价格最高 €116.90（AirPods 4）

---

### [2026-03-27] eBay 错误处理

**问题**：`EBAY_APP_ID=your_ebay_app_id_here` 占位符导致 eBay API 返回 HTTP 500，pipeline 整体崩溃

**修复**：`scrapers/ebay_de.py` 中将 `resp.raise_for_status()` 包裹 `try/except HTTPError`，失败时 log warning 并 `return`（返回空迭代器）

**效果**：eBay 未配置时 pipeline 继续正常运行，不影响其他数据

---

### [2026-03-27] Pipeline 端到端验证

**完整运行结果**（10 个关键词，`scheduler/main.py`）：

```
AliExpress   : 102 条（平均 10.2/关键词）
Amazon.de    : 500 条（50/关键词，稳定）
eBay.de      : 0 条（EBAY_APP_ID 未配置，跳过）
去重+过滤后  : 486 条
利润率≥30%   : 138 条
快照保存     : data/raw/snapshot_20260327_104912.json ✅
Google Sheets: ❌ API 未启用（见下方）
```

**Top 3 利润商品**：

| 品类 | 进价 EUR | 售价 EUR | 利润率 |
|------|---------|---------|--------|
| LED Streifen | €1.05 | €89.99 | **79.9%** |
| LED Streifen | €1.05 | €78.13 | 79.2% |
| Bluetooth Kopfhörer | €13.81 | €116.90 | 70.2% |

**品类均利润率排行**：

| 品类 | 件数 | 均利润率 |
|------|------|---------|
| LED Streifen | 41 | **59.3%** |
| Yoga Matte | 1 | 62.3% |
| Bluetooth Kopfhörer | 17 | 46.7% |
| USB Hub | 18 | 45.4% |
| Haustier Zubehör | 5 | 44.9% |
| Fitnessband | 15 | 41.7% |
| Handyhülle iPhone | 41 | 41.2% |

---

### [2026-03-27] Scheduler 容错修复

**问题**：Google Sheets API 未启用导致 pipeline crash，快照虽保存但程序异常退出

**修复**：`scheduler/main.py` 将 `write_products()` 调用包裹 `try/except Exception`，失败时输出含启用链接的 warning，程序正常结束

---

---

## Sprint 3 — VPS 部署与云同步架构

### [2026-03-27] VPS 部署（RackNerd via Tailscale）

**目标**：将 pipeline 部署到 VPS，实现 24h 自动运行，建立安全的代码+密钥同步机制

**VPS 环境**：
- OS：Ubuntu 22.04 LTS，Python 3.12.3
- Tailscale hostname：`racknerd-32738e2.tail27b5c.ts.net`，IP：`100.125.28.79`
- 磁盘：24GB（剩余 6.9GB），内存：961MB（swap 5GB）

**部署步骤**：
1. VPS 通过 SSH（Tailscale 加密隧道）可达，Python 3.12 + pip3 + git 预装 ✅
2. `git clone https://github.com/wyl2607/meichen.git /opt/meichen` 从 GitHub 拉取代码
3. `scp .env credentials.json root@100.125.28.79:/opt/meichen/`（Tailscale 加密，密钥不经明文网络）
4. VPS 上创建 Python venv，`pip install -r requirements.txt`
5. 密钥文件权限加固：`chmod 600 .env credentials.json`
6. 创建 `/etc/systemd/system/meichen-scout.service`，开机自启

**VPS Pipeline 验证结果**（单关键词 LED Streifen）：
- AliExpress：11 条
- Amazon.de：50 条
- 利润率 ≥30%：37 条
- Top 商品：78.6% 利润率 ✅

**新增文件**：
- `CLAUDE.md`：Claude Code 项目上下文文档（架构、命令、踩坑记录）
- `sync.sh`：一键同步脚本（代码走 GitHub，密钥走 Tailscale SCP）

**云备份策略（安全优先）**：

| 类型 | 存储位置 | 传输方式 | 安全级别 |
|------|---------|---------|---------|
| 代码 | GitHub wyl2607/meichen（public） | HTTPS push | ✅ 无敏感信息 |
| 密钥（.env） | VPS /opt/meichen/（chmod 600） | Tailscale SCP | ✅ E2E 加密 |
| 密钥（credentials.json） | VPS /opt/meichen/（chmod 600） | Tailscale SCP | ✅ E2E 加密 |
| 数据快照 | VPS data/raw/ + 本地 data/raw/ | 双份本地 | ✅ 不上云 |

---

## 当前状态总览

```
┌─────────────────────────┬────────────────────────────────────────────────┐
│  组件                   │  状态                                          │
├─────────────────────────┼────────────────────────────────────────────────┤
│  AliExpress 爬虫        │  ✅ 正常（已修复选择器）                        │
│  Amazon.de 爬虫         │  ✅ 正常（已修复 title/URL 选择器）             │
│  eBay.de 爬虫           │  ⚠️  跳过（需填入 EBAY_APP_ID）                 │
│  利润计算器             │  ✅ 正常                                        │
│  去重/过滤              │  ✅ 正常                                        │
│  定时调度               │  ✅ 正常（每 24h）                              │
│  原始快照保存           │  ✅ 正常（data/raw/）                           │
│  Google Sheets 写入     │  ⚠️  待操作（需启用 Sheets API + Drive API）    │
│  GitHub 仓库            │  ✅ 最新代码已推送（wyl2607/meichen main）      │
│  VPS 部署               │  ✅ 运行中（systemd，每 24h，100.125.28.79）   │
│  云同步脚本             │  ✅ sync.sh（代码→GitHub，密钥→Tailscale SCP） │
└─────────────────────────┴────────────────────────────────────────────────┘
```

---

## 待办事项（Next Actions）

| 优先级 | 事项 | 操作人 | 说明 |
|--------|------|--------|------|
| 🔴 高 | 启用 Google Sheets API | 用户 | 访问 GCP Console，project=1098098407491 |
| 🔴 高 | 启用 Google Drive API | 用户 | 同上，Drive API 也需要启用 |
| 🟡 中 | 配置 eBay App ID | 用户 | 申请地址：developer.ebay.com |
| 🟡 中 | 删除 GitHub master 分支 | 用户 | 先在 GitHub Settings 将默认分支改为 main |
| 🟡 中 | 查看 VPS 每日结果 | 用户 | `bash sync.sh --logs` 或 SSH 到 VPS 查看 |
| 🟢 低 | 接入 Amazon PA-API 5.0 | 工程 | 替代直接 HTML 抓取，更稳定 |
| 🟢 低 | 定期维护 AliExpress 选择器 | 工程 | AliExpress 频繁改版，建议每月检查 |

---

## Git 提交记录

| Commit | 描述 |
|--------|------|
| `6a0ea8a` | fix: update scrapers to match current DOM structure |
| `3b685c4` | fix: make Google Sheets write non-fatal in pipeline |
| `10523d0` | docs: add REQUIREMENTS.md and PROGRESS.md |
