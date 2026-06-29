"""Flipkart product checker: PID extraction, pincode, stock & price signals."""
from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from app.logger import get_logger
from app.stores.base import StockResult, StoreChecker

logger = get_logger(__name__)

PID_RE = re.compile(r"pid=([A-Z0-9]+)", re.IGNORECASE)
ITM_RE = re.compile(r"/(itm[0-9a-zA-Z]+)")
PRICE_RE = re.compile(r"^₹[0-9,]+$")


class FlipkartChecker(StoreChecker):
    name = "flipkart"

    @staticmethod
    def extract_product_id(url: str) -> Optional[str]:
        if "flipkart.com" not in url:
            return None
        match = PID_RE.search(url)
        if match:
            return match.group(1).upper()
        match = ITM_RE.search(url)
        if match:
            return match.group(1)
        return None

    def apply_pincode(self, page: Page, pincode: str) -> bool:
        try:
            pincode_input = page.get_by_placeholder("Enter Delivery Pincode")
            if pincode_input.first.is_visible(timeout=3000):
                pincode_input.first.fill(pincode)
                page.get_by_text("Check", exact=True).first.click(timeout=3000)
                page.wait_for_timeout(1500)
                logger.info("Applied Flipkart pincode %s", pincode)
                return True
        except PlaywrightTimeoutError:
            logger.debug("No Flipkart pincode prompt found; address likely already saved")
        except Exception as exc:
            logger.warning("Could not set Flipkart pincode: %s", exc)
        return False

    def get_stock_status(self, page: Page) -> StockResult:
        title = self._get_title(page)
        price = self._get_price(page)
        signals = self._collect_signals(page)
        logger.info("Flipkart stock signals: %s", signals)

        positive = signals["buy_now"] or signals["add_to_cart"]
        negative = signals["sold_out"] or signals["unavailable"] or signals["delivery_unavailable"]

        if negative:
            status = "OUT_OF_STOCK"
        elif positive:
            status = "IN_STOCK"
        else:
            status = "UNKNOWN"

        return StockResult(status=status, price=price, title=title)

    def _get_title(self, page: Page) -> str:
        # The on-page <h1> is visually truncated with "...more" by Flipkart's
        # UI, so the document title is the reliable full string.
        title = page.title()
        if title:
            return title.strip()
        try:
            heading = page.get_by_role("heading").first
            return heading.inner_text(timeout=5000).strip()
        except Exception:
            return ""

    def _collect_signals(self, page: Page) -> dict:
        def visible(locator) -> bool:
            try:
                return locator.first.is_visible(timeout=3000)
            except Exception:
                return False

        return {
            "buy_now": visible(page.get_by_role("button", name="BUY NOW"))
            or visible(page.get_by_text("Buy Now", exact=False)),
            "add_to_cart": visible(page.get_by_role("button", name="ADD TO CART"))
            or visible(page.get_by_text("Add to cart", exact=False)),
            "sold_out": visible(page.get_by_text("Sold Out", exact=False)),
            "unavailable": visible(page.get_by_text("Currently Unavailable", exact=False)),
            "delivery_unavailable": visible(page.get_by_text("Delivery unavailable", exact=False))
            or visible(page.get_by_text("not deliverable", exact=False)),
        }

    def _get_price(self, page: Page) -> Optional[str]:
        try:
            price_locator = page.get_by_text(PRICE_RE)
            if price_locator.first.is_visible(timeout=3000):
                return price_locator.first.inner_text().strip()
        except Exception:
            pass
        # Legacy Flipkart price class, kept only as a last resort.
        try:
            legacy = page.locator("div._30jeq3").first
            if legacy.is_visible(timeout=2000):
                return legacy.inner_text().strip()
        except Exception:
            pass
        return None
