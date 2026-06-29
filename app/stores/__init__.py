"""Registry mapping store names to their StoreChecker implementation."""
from __future__ import annotations

from typing import Optional, Tuple

from app.stores.amazon import AmazonChecker
from app.stores.base import StoreChecker
from app.stores.flipkart import FlipkartChecker

CHECKERS = {
    "flipkart": FlipkartChecker(),
    "amazon": AmazonChecker(),
}


def detect_store(url: str) -> Optional[Tuple[str, str]]:
    """Return (store_name, product_id) if `url` matches a supported store."""
    for name, checker in CHECKERS.items():
        product_id = checker.extract_product_id(url)
        if product_id:
            return name, product_id
    return None


def get_checker(store: str) -> StoreChecker:
    return CHECKERS[store]
