"""
Scheduler entry point — orchestrates daily scraping, processing, and storage.
Run: python scheduler/main.py  (from project root)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time

# Ensure project root is on sys.path regardless of where the script is launched from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from pathlib import Path

import schedule

from config import (
    DATA_RAW_PATH,
    SCHEDULE_INTERVAL_HOURS,
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
    log.info("Pipeline started — %s", datetime.utcnow().isoformat())
    raw_products: list[Product] = []

    for keyword in SEARCH_KEYWORDS:
        log.info("Scraping keyword: %s", keyword)

        # 1. Source prices from AliExpress
        ali_products = list(aliexpress.scrape_keyword(keyword))
        log.info("  AliExpress: %d items", len(ali_products))

        # 2. Sell prices from Amazon.de (use average source price as placeholder)
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

    # 7. Write to Google Sheets (non-fatal — pipeline succeeds even if Sheets is misconfigured)
    try:
        written = write_products(profitable)
        log.info("Written to Sheets: %d rows", written)
    except Exception as e:
        log.warning(
            "Google Sheets write skipped (%s). "
            "Enable the API at: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview "
            "and ensure the sheet is shared with the service account.",
            e,
        )
        written = 0
    log.info("Pipeline complete. Profitable products found: %d", len(profitable))


def _save_raw(products: list[Product]) -> None:
    path = Path(DATA_RAW_PATH)
    path.mkdir(parents=True, exist_ok=True)
    filename = path / f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            [p.__dict__ | {"scraped_at": p.scraped_at.isoformat()} for p in products],
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    log.info("Raw snapshot saved: %s", filename)


if __name__ == "__main__":
    log.info("Scheduler starting — interval: every %d hours", SCHEDULE_INTERVAL_HOURS)
    run_pipeline()   # run immediately on start
    schedule.every(SCHEDULE_INTERVAL_HOURS).hours.do(run_pipeline)
    while True:
        schedule.run_pending()
        time.sleep(60)
