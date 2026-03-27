"""
Amazon.de scraper — extracts product title, price, image, and URL.
Uses requests + BeautifulSoup; falls back to Selenium for JS-heavy pages.
"""
from __future__ import annotations

import random
import time
import uuid
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from config import (
    AMAZON_DE_BASE_URL,
    MAX_RESULTS_PER_KEYWORD,
    REQUEST_DELAY_JITTER,
    REQUEST_DELAY_SECONDS,
    SCRAPER_API_KEY,
)
from models import Product


# 多个真实浏览器 UA，每次请求随机选一个，降低被识别为爬虫的风险
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def _make_headers() -> dict:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
    }


def _parse_price(text: str) -> float | None:
    """Convert '12,99' or '12.99' to float."""
    try:
        return float(text.replace(".", "").replace(",", ".").strip())
    except (ValueError, AttributeError):
        return None


def scrape_keyword(keyword: str, source_price_eur: float, source_price_cny: float) -> Iterator[Product]:
    """Yield Product objects for a given search keyword on Amazon.de."""
    search_url = f"{AMAZON_DE_BASE_URL}/s?k={requests.utils.quote(keyword)}&language=de_DE"
    collected = 0

    while search_url and collected < MAX_RESULTS_PER_KEYWORD:
        try:
            resp = requests.get(search_url, headers=_make_headers(), timeout=15)
            if resp.status_code in (429, 503):
                import logging
                logging.getLogger(__name__).warning(
                    "Amazon.de 返回 %d（限速/封禁信号），跳过关键词 %r，明天再试",
                    resp.status_code, keyword,
                )
                return
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            import logging
            logging.getLogger(__name__).warning("Amazon.de 请求失败 (%s)，跳过关键词 %r", e, keyword)
            return
        soup = BeautifulSoup(resp.text, "lxml")

        for card in soup.select('[data-component-type="s-search-result"]'):
            if collected >= MAX_RESULTS_PER_KEYWORD:
                break

            # Title: "h2 span" works; "h2 a span" breaks when anchor wraps differently
            title_el = card.select_one("h2 span")
            price_whole = card.select_one(".a-price-whole")
            price_frac = card.select_one(".a-price-fraction")
            img_el = card.select_one("img.s-image")

            if not (title_el and price_whole):
                continue

            price_str = price_whole.get_text() + (price_frac.get_text() if price_frac else "00")
            amazon_price = _parse_price(price_str)
            if amazon_price is None:
                continue

            # Build URL from ASIN (most reliable) or from any /dp/ link on the card
            asin = card.get("data-asin", "")
            if asin:
                product_url = f"{AMAZON_DE_BASE_URL}/dp/{asin}"
            else:
                dp_link = card.select_one('a[href*="/dp/"]')
                product_url = (AMAZON_DE_BASE_URL + dp_link["href"]) if dp_link else None
                asin = str(uuid.uuid4())

            yield Product(
                product_id=f"amz_{asin}",
                title=title_el.get_text(strip=True),
                source_platform="aliexpress",
                source_price_cny=source_price_cny,
                source_price_eur=source_price_eur,
                amazon_price_eur=amazon_price,
                ebay_price_eur=None,
                estimated_shipping_eur=0.0,   # filled by profit_calculator
                profit_margin=0.0,             # filled by profit_calculator
                search_keyword=keyword,
                image_url=img_el["src"] if img_el else None,
                product_url=product_url,
            )
            collected += 1

        # Pagination
        next_el = soup.select_one("a.s-pagination-next")
        search_url = (AMAZON_DE_BASE_URL + next_el["href"]) if next_el else None
        time.sleep(REQUEST_DELAY_SECONDS + random.uniform(0, REQUEST_DELAY_JITTER))
