"""
Profit calculator — enriches Product records with shipping estimate and margin.
"""
from __future__ import annotations

from config import (
    AMAZON_DE_BASE_URL,
    DEFAULT_SHIPPING_EUR,
    EBAY_FEE_RATE,
    FBA_FEE_RATE,
    MIN_PROFIT_MARGIN,
)
from models import Product


def calculate(product: Product) -> Product:
    """
    Return a new Product with estimated_shipping_eur and profit_margin filled in.
    Margin is computed against the best available sell price after platform fees.
    """
    shipping = DEFAULT_SHIPPING_EUR

    amazon_net = None
    if product.amazon_price_eur is not None:
        amazon_net = product.amazon_price_eur * (1 - FBA_FEE_RATE) - shipping - product.source_price_eur

    ebay_net = None
    if product.ebay_price_eur is not None:
        ebay_net = product.ebay_price_eur * (1 - EBAY_FEE_RATE) - shipping - product.source_price_eur

    nets = [n for n in [amazon_net, ebay_net] if n is not None]
    best_net = max(nets) if nets else 0.0

    # Use best sell price as denominator; guard against zero
    best_sell = product.best_sell_price() or 1.0
    margin = round(best_net / best_sell, 4)

    return Product(
        **{**product.__dict__, "estimated_shipping_eur": shipping, "profit_margin": margin}
    )


def is_profitable(product: Product) -> bool:
    return product.profit_margin >= MIN_PROFIT_MARGIN
