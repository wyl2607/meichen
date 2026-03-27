"""
AliExpress scraper — retrieves source (supply) price in CNY.
Uses ScraperAPI proxy to bypass bot detection.
"""
from __future__ import annotations

import time
import uuid
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from config import (
    ALIEXPRESS_BASE_URL,
    CNY_TO_EUR,
    MAX_RESULTS_PER_KEYWORD,
    REQUEST_DELAY_SECONDS,
    SCRAPER_API_KEY,
)
from models import Product


def _scraper_api_url(target: str) -> str:
    return f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={requests.utils.quote(target)}"


def _parse_price_cny(text: str) -> float | None:
    """Extract numeric price from strings like 'US $3.45' or '¥23.00'."""
    import re
    match = re.search(r"[\d,.]+", text.replace(",", "."))
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def scrape_keyword(keyword: str) -> Iterator[Product]:
    """Yield Product objects with source pricing for a given keyword.

    ScraperAPI routes via EU IP so AliExpress returns prices in EUR.
    We store as source_price_eur and back-calculate source_price_cny.
    """
    search_url = f"{ALIEXPRESS_BASE_URL}/wholesale?SearchText={requests.utils.quote(keyword)}"
    collected = 0

    try:
        resp = requests.get(_scraper_api_url(search_url), timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        import logging
        logging.getLogger(__name__).warning("AliExpress fetch error: %s", e)
        return

    soup = BeautifulSoup(resp.text, "lxml")

    # Current selector as of 2025: container = .search-item-card-wrapper-gallery
    # price in .lw_kt (discounted/current price), title in h3, link in a.search-card-item
    for item in soup.select(".search-item-card-wrapper-gallery"):
        if collected >= MAX_RESULTS_PER_KEYWORD:
            break

        title_el = item.select_one("h3")
        price_el = item.select_one(".lw_kt")   # current/sale price in EUR
        img_el = item.select_one("img")
        link_el = item.select_one("a.search-card-item") or item.select_one("a")

        if not (title_el and price_el):
            continue

        # Price is displayed in EUR by ScraperAPI EU routing
        price_eur = _parse_price_cny(price_el.get_text(strip=True))
        if price_eur is None or price_eur <= 0:
            continue

        price_cny = round(price_eur / CNY_TO_EUR, 2)
        href = link_el.get("href", "") if link_el else ""
        product_url = ("https:" + href) if href.startswith("//") else href or None

        yield Product(
            product_id=f"ali_{uuid.uuid4().hex[:12]}",
            title=title_el.get_text(strip=True),
            source_platform="aliexpress",
            source_price_cny=price_cny,
            source_price_eur=price_eur,
            amazon_price_eur=None,
            ebay_price_eur=None,
            estimated_shipping_eur=0.0,
            profit_margin=0.0,
            search_keyword=keyword,
            image_url=img_el.get("src") or img_el.get("data-src") if img_el else None,
            product_url=product_url,
        )
        collected += 1
        time.sleep(REQUEST_DELAY_SECONDS)
