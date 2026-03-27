"""
Pipeline entry point — orchestrates daily scraping, processing, and storage.

设计原则：
  本脚本是一次性运行（one-shot）。调度由外部 systemd timer 负责，
  不在进程内维持 while loop，避免内存常驻、崩溃后卡死等问题。

运行方式：
  python scheduler/main.py           # 直接运行一次
  systemctl start meichen-scout      # 由 systemd 触发（推荐）
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path regardless of where the script is launched from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    DATA_RAW_PATH,
    SCRAPER_API_MAX_CALLS_PER_RUN,
    SEARCH_KEYWORDS,
)
from models import Product
from processors.cleaner import deduplicate, filter_valid
from processors.profit_calculator import calculate, is_profitable
from scrapers import aliexpress, amazon_de, ebay_de
from storage.sheets_writer import write_products

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def run_pipeline() -> None:
    start_time = datetime.now(timezone.utc)
    log.info("=" * 60)
    log.info("Pipeline started — %s", start_time.isoformat())
    log.info("ScraperAPI 单次上限: %d 次", SCRAPER_API_MAX_CALLS_PER_RUN)
    raw_products: list[Product] = []

    for keyword in SEARCH_KEYWORDS:
        log.info("Scraping keyword: %s", keyword)

        # 1. Source prices from AliExpress (via ScraperAPI EU proxy)
        ali_products = list(aliexpress.scrape_keyword(keyword))
        log.info("  AliExpress: %d items", len(ali_products))

        # 2. Sell prices from Amazon.de
        avg_cny = sum(p.source_price_cny for p in ali_products) / max(len(ali_products), 1)
        avg_eur = sum(p.source_price_eur for p in ali_products) / max(len(ali_products), 1)
        amz_products = list(amazon_de.scrape_keyword(keyword, avg_eur, avg_cny))
        log.info("  Amazon.de: %d items", len(amz_products))

        # 3. Sell prices from eBay.de
        ebay_products = list(ebay_de.scrape_keyword(keyword))
        log.info("  eBay.de: %d items", len(ebay_products))

        raw_products.extend(ali_products + amz_products + ebay_products)

    # 4. Clean
    cleaned = deduplicate(filter_valid(raw_products))
    log.info("After dedup+filter: %d products", len(cleaned))

    # 5. Calculate profit
    enriched = [calculate(p) for p in cleaned]
    profitable = [p for p in enriched if is_profitable(p)]
    log.info("Profitable (≥ threshold): %d products", len(profitable))

    # 6. Save raw snapshot
    _save_raw(enriched)

    # 7. Write to Google Sheets (non-fatal)
    try:
        written = write_products(profitable)
        log.info("Written to Sheets: %d rows", written)
    except Exception as e:
        log.warning(
            "Google Sheets write skipped (%s). "
            "Enable: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview",
            e,
        )
        written = 0

    elapsed = (datetime.now(timezone.utc) - start_time).seconds
    log.info("Pipeline complete. profitable=%d written=%d elapsed=%ds",
             len(profitable), written, elapsed)
    log.info("=" * 60)

    # 8. 清理超过 30 天的旧快照，防止磁盘占满
    _cleanup_old_snapshots(keep_days=30)


def _save_raw(products: list[Product]) -> None:
    path = Path(DATA_RAW_PATH)
    path.mkdir(parents=True, exist_ok=True)
    filename = path / f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            [p.__dict__ | {"scraped_at": p.scraped_at.isoformat()} for p in products],
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    log.info("Raw snapshot saved: %s", filename)


def _cleanup_old_snapshots(keep_days: int = 30) -> None:
    """删除超过 keep_days 天的旧快照，防止 VPS 磁盘占满。"""
    import time
    path = Path(DATA_RAW_PATH)
    if not path.exists():
        return
    cutoff = time.time() - keep_days * 86400
    removed = 0
    for f in path.glob("snapshot_*.json"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    if removed:
        log.info("Cleaned up %d old snapshot(s) (>%d days)", removed, keep_days)


if __name__ == "__main__":
    run_pipeline()
