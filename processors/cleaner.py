"""
Data cleaner — deduplicates and normalises raw Product records.
"""
from __future__ import annotations

import re
from collections import defaultdict

from models import Product


def deduplicate(products: list[Product]) -> list[Product]:
    """Keep the highest-priced listing per normalised title."""
    buckets: dict[str, Product] = {}
    for p in products:
        key = _normalise_title(p.title)
        existing = buckets.get(key)
        if existing is None:
            buckets[key] = p
        else:
            # Prefer the record with more price data
            if (p.amazon_price_eur or 0) + (p.ebay_price_eur or 0) > \
               (existing.amazon_price_eur or 0) + (existing.ebay_price_eur or 0):
                buckets[key] = p
    return list(buckets.values())


def _normalise_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9äöüß ]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    # Remove stop words that vary across platforms
    stop = {"für", "mit", "und", "the", "for", "with", "set", "stück", "pack"}
    return " ".join(w for w in title.split() if w not in stop)


def filter_valid(products: list[Product]) -> list[Product]:
    """Drop products missing both sell-side prices."""
    return [
        p for p in products
        if p.amazon_price_eur is not None or p.ebay_price_eur is not None
    ]
