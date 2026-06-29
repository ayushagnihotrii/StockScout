"""Common interface every store-specific checker implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page


@dataclass
class StockResult:
    status: str  # IN_STOCK / OUT_OF_STOCK / UNKNOWN
    price: Optional[str]
    title: str


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


class StoreChecker(ABC):
    name: str

    @staticmethod
    @abstractmethod
    def extract_product_id(url: str) -> Optional[str]:
        """Return the store's canonical product id, or None if `url` doesn't
        belong to this store."""

    @staticmethod
    def normalize_url(url: str) -> str:
        """Rewrite a share/short link to a directly-navigable canonical URL.
        Default is a no-op; override for stores with share-link domains
        that don't load reliably in an automated browser."""
        return url

    @abstractmethod
    def apply_pincode(self, page: Page, pincode: str) -> bool:
        """Fill in the delivery pincode if prompted. Returns True if it was
        actually applied (used to flag possibly-wrong-region results)."""

    @abstractmethod
    def get_stock_status(self, page: Page) -> StockResult:
        ...

    def validate(self, page: Page, expected_product_id: str) -> ValidationResult:
        """Confirm the page still resolves to the product we registered --
        guards against redirects to a different/error page."""
        current = self.extract_product_id(page.url)
        if current != expected_product_id:
            return ValidationResult(
                False,
                f"Product id changed: expected {expected_product_id!r}, got {current!r} at {page.url}",
            )
        return ValidationResult(True)
