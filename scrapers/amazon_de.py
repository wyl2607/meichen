"""
Amazon.de scraper — extracts product title, price, image, and URL.
Uses requests + BeautifulSoup; falls back to Selenium for JS-heavy pages.
"""
from __future__ import annotations

import time
import uuid
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from config import (
    AMAZON_DE_BASE_URL,
    MAX_RESULTS_PER_KEYWORD,
    REQUEST_DELAY_SECONDS,
    SCRAPER_API_KEY,
)
from models import Product


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
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
        resp = requests.get(search_url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for card in soup.select('[data-component-type="s-search-result"]'):
            if collected >= MAX_RESULTS_PER_KEYWORD:
                break

            title_el = card.select_one("h2 a span")
            price_whole = card.select_one(".a-price-whole")
            price_frac = card.select_one(".a-price-fraction")
            img_el = card.select_one("img.s-image")
            link_el = card.select_one("h2 a")

            if not (title_el and price_whole):
                continue

            price_str = price_whole.get_text() + (price_frac.get_text() if price_frac else "00")
            amazon_price = _parse_price(price_str)
            if amazon_price is None:
                continue

            product_url = AMAZON_DE_BASE_URL + link_el["href"] if link_el else None
            asin = card.get("data-asin", str(uuid.uuid4()))

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
        time.sleep(REQUEST_DELAY_SECONDS)
