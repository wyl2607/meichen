from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Product:
    product_id: str
    title: str
    source_platform: str          # "aliexpress" | "1688" | "taobao"
    source_price_cny: float
    source_price_eur: float
    amazon_price_eur: Optional[float]
    ebay_price_eur: Optional[float]
    estimated_shipping_eur: float
    profit_margin: float          # 0.0 ~ 1.0, e.g. 0.35 = 35%
    search_keyword: str
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    image_url: Optional[str] = None
    product_url: Optional[str] = None

    def best_sell_price(self) -> Optional[float]:
        """Return the higher of amazon/ebay price for comparison."""
        prices = [p for p in [self.amazon_price_eur, self.ebay_price_eur] if p is not None]
        return max(prices) if prices else None

    def gross_profit_eur(self) -> Optional[float]:
        sell = self.best_sell_price()
        if sell is None:
            return None
        return sell - self.source_price_eur - self.estimated_shipping_eur
