import os
from dotenv import load_dotenv

load_dotenv()

# ── 汇率 ─────────────────────────────────────────────────────────────────────
CNY_TO_EUR: float = float(os.getenv("CNY_TO_EUR", "0.127"))   # 1 CNY = 0.127 EUR (update daily)

# ── 搜索关键词 ─────────────────────────────────────────────────────────────────
SEARCH_KEYWORDS: list[str] = [
    "LED Streifen",
    "Handyhülle iPhone",
    "Fitnessband",
    "Küchen Gadget",
    "Haustier Zubehör",
    "Bluetooth Kopfhörer",
    "USB Hub",
    "Garten Werkzeug",
    "Baby Spielzeug",
    "Yoga Matte",
]

# ── 利润率阈值 ──────────────────────────────────────────────────────────────────
MIN_PROFIT_MARGIN: float = 0.30          # 30% 最低净利润率
TARGET_PROFIT_MARGIN: float = 0.45       # 45% 目标净利润率
MAX_SOURCE_PRICE_EUR: float = 15.0       # 最高采购价（EUR），超过不考虑
MIN_SELL_PRICE_EUR: float = 9.99         # 最低上架价（EUR），低于不考虑

# ── 物流估算 ──────────────────────────────────────────────────────────────────
DEFAULT_SHIPPING_EUR: float = 3.50       # 小包直发平均运费
FBA_FEE_RATE: float = 0.15              # Amazon FBA 费率（售价 × 15%）
EBAY_FEE_RATE: float = 0.13             # eBay 最终价值费（售价 × 13%）

# ── API 密钥 (从 .env 读取，不硬编码) ──────────────────────────────────────────
SCRAPER_API_KEY: str = os.getenv("SCRAPER_API_KEY", "REPLACE_ME")
GOOGLE_SHEETS_CREDS_FILE: str = os.getenv("GOOGLE_SHEETS_CREDS_FILE", "credentials.json")
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "REPLACE_ME")

AMAZON_AFFILIATE_TAG: str = os.getenv("AMAZON_AFFILIATE_TAG", "")
EBAY_APP_ID: str = os.getenv("EBAY_APP_ID", "REPLACE_ME")
EBAY_CERT_ID: str = os.getenv("EBAY_CERT_ID", "REPLACE_ME")

# ── 爬虫行为 ──────────────────────────────────────────────────────────────────
REQUEST_DELAY_SECONDS: float = 2.0      # 每次请求间隔（秒）
MAX_RESULTS_PER_KEYWORD: int = 50       # 每个关键词最多抓取商品数
HEADLESS_BROWSER: bool = True           # Selenium 是否无头模式

# ── 目标站点 URL ───────────────────────────────────────────────────────────────
AMAZON_DE_BASE_URL: str = "https://www.amazon.de"
EBAY_DE_BASE_URL: str = "https://www.ebay.de"
ALIEXPRESS_BASE_URL: str = "https://www.aliexpress.com"

# ── 调度 ──────────────────────────────────────────────────────────────────────
SCHEDULE_INTERVAL_HOURS: int = 24       # 每天运行一次
DATA_RAW_PATH: str = "data/raw"
