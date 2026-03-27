"""
Google Sheets writer — appends profitable products to a configured spreadsheet.
"""
from __future__ import annotations

from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_ID, GOOGLE_SHEETS_CREDS_FILE
from models import Product

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

_HEADERS = [
    "product_id", "title", "source_platform",
    "source_price_cny", "source_price_eur",
    "amazon_price_eur", "ebay_price_eur",
    "estimated_shipping_eur", "profit_margin",
    "search_keyword", "scraped_at",
    "image_url", "product_url",
]


def _get_worksheet(sheet_name: str = "Products") -> gspread.Worksheet:
    creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDS_FILE, scopes=_SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=sheet_name, rows=5000, cols=len(_HEADERS))
        ws.append_row(_HEADERS)
    return ws


def write_products(products: list[Product], sheet_name: str = "Products") -> int:
    """Append products to Google Sheets. Returns count of rows written."""
    if not products:
        return 0

    ws = _get_worksheet(sheet_name)
    rows = [_to_row(p) for p in products]
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)


def _to_row(p: Product) -> list:
    return [
        p.product_id,
        p.title,
        p.source_platform,
        p.source_price_cny,
        p.source_price_eur,
        p.amazon_price_eur,
        p.ebay_price_eur,
        p.estimated_shipping_eur,
        round(p.profit_margin * 100, 2),   # store as percentage
        p.search_keyword,
        p.scraped_at.isoformat() if isinstance(p.scraped_at, datetime) else str(p.scraped_at),
        p.image_url or "",
        p.product_url or "",
    ]
