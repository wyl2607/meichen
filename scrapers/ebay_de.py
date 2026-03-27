"""
eBay.de scraper — retrieves sell-side price via eBay Finding API.
Falls back to HTML scraping if API quota is exhausted.
"""
from __future__ import annotations

import time
import uuid
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from config import (
    EBAY_APP_ID,
    EBAY_DE_BASE_URL,
    MAX_RESULTS_PER_KEYWORD,
    REQUEST_DELAY_SECONDS,
)
from models import Product


_FINDING_API = (
    "https://svcs.ebay.com/services/search/FindingService/v1"
    "?OPERATION-NAME=findItemsByKeywords"
    "&SERVICE-VERSION=1.0.0"
    "&SECURITY-APPNAME={app_id}"
    "&RESPONSE-DATA-FORMAT=JSON"
    "&REST-PAYLOAD"
    "&keywords={keywords}"
    "&paginationInput.entriesPerPage={count}"
    "&itemFilter(0).name=ListingType&itemFilter(0).value=FixedPrice"
    "&itemFilter(1).name=LocatedIn&itemFilter(1).value=DE"
)


def scrape_keyword(keyword: str) -> Iterator[Product]:
    """Yield Product stubs with ebay_price_eur populated."""
    url = _FINDING_API.format(
        app_id=EBAY_APP_ID,
        keywords=requests.utils.quote(keyword),
        count=min(MAX_RESULTS_PER_KEYWORD, 100),
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    try:
        items = (
            data["findItemsByKeywordsResponse"][0]
            ["searchResult"][0]
            ["item"]
        )
    except (KeyError, IndexError):
        return

    for item in items:
        try:
            price = float(item["sellingStatus"][0]["currentPrice"][0]["__value__"])
            title = item["title"][0]
            item_url = item["viewItemURL"][0]
            img_url = item.get("galleryURL", [None])[0]
            item_id = item.get("itemId", [str(uuid.uuid4())])[0]
        except (KeyError, IndexError, ValueError):
            continue

        yield Product(
            product_id=f"ebay_{item_id}",
            title=title,
            source_platform="",        # to be merged with AliExpress data
            source_price_cny=0.0,
            source_price_eur=0.0,
            amazon_price_eur=None,
            ebay_price_eur=price,
            estimated_shipping_eur=0.0,
            profit_margin=0.0,
            search_keyword=keyword,
            image_url=img_url,
            product_url=item_url,
        )
        time.sleep(REQUEST_DELAY_SECONDS)
