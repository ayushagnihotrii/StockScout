"""Amazon product checker: ASIN extraction, pincode, stock & price signals.

Amazon rate-limits/CAPTCHAs automated traffic far more aggressively than
Flipkart, especially from shared datacenter IPs like GitHub-hosted
runners. This checker degrades to UNKNOWN whenever it detects a captcha
page or can't confirm a signal, rather than guessing and risking a false
notification.
"""
from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Page

from app.logger import get_logger
from app.stores.base import StockResult, StoreChecker

logger = get_logger(__name__)

ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})", re.IGNORECASE)
CAPTCHA_TEXT_RE = re.compile(r"Type the characters you see", re.IGNORECASE)
PRICE_RE = re.compile(r"^[₹$][0-9,]+(\.[0-9]{2})?$")
DELIVER_TO_RE = re.compile(r"Deliver to|location", re.IGNORECASE)
APPLY_RE = re.compile(r"Apply|Done", re.IGNORECASE)


class AmazonChecker(StoreChecker):
    name = "amazon"

    @staticmethod
    def extract_product_id(url: str) -> Optional[str]:
        if "amazon." not in url:
            return None
        match = ASIN_RE.search(url)
        if match:
            return match.group(1).upper()
        return None

    def apply_pincode(self, page: Page, pincode: str) -> bool:
        try:
            opener = page.get_by_role("button", name=DELIVER_TO_RE)
            if not opener.first.is_visible(timeout=3000):
                opener = page.locator("#nav-global-location-popover-link")
            if opener.first.is_visible(timeout=3000):
                opener.first.click(timeout=3000)
                page.wait_for_timeout(1000)

            zip_input = page.locator("#GLUXZipUpdateInput")
            if not zip_input.first.is_visible(timeout=3000):
                zip_input = page.get_by_placeholder(re.compile("pincode|zip", re.IGNORECASE))
            if zip_input.first.is_visible(timeout=3000):
                zip_input.first.fill(pincode)
                apply_button = page.locator("#GLUXZipUpdate")
                if apply_button.first.is_visible(timeout=2000):
                    apply_button.first.click(timeout=3000)
                else:
                    page.get_by_role("button", name=APPLY_RE).first.click(timeout=3000)
                page.wait_for_timeout(2000)
                logger.info("Applied Amazon pincode %s", pincode)
                return True
        except Exception as exc:
            logger.warning("Could not set Amazon pincode: %s", exc)
        return False

    def _is_captcha(self, page: Page) -> bool:
        if "validateCaptcha" in page.url:
            return True
        try:
            return page.get_by_text(CAPTCHA_TEXT_RE).first.is_visible(timeout=2000)
        except Exception:
            return False

    def get_stock_status(self, page: Page) -> StockResult:
        title = (page.title() or "").strip()

        if self._is_captcha(page):
            logger.warning("Amazon captcha/block page detected, returning UNKNOWN")
            return StockResult(status="UNKNOWN", price=None, title=title)

        price = self._get_price(page)
        signals = self._collect_signals(page)
        logger.info("Amazon stock signals: %s", signals)

        positive = signals["add_to_cart"] or signals["buy_now"]
        negative = signals["unavailable"] or signals["out_of_stock"]

        if negative:
            status = "OUT_OF_STOCK"
        elif positive:
            status = "IN_STOCK"
        else:
            status = "UNKNOWN"

        return StockResult(status=status, price=price, title=title)

    def _collect_signals(self, page: Page) -> dict:
        def visible(locator) -> bool:
            try:
                return locator.first.is_visible(timeout=3000)
            except Exception:
                return False

        return {
            "add_to_cart": visible(page.locator("#add-to-cart-button"))
            or visible(page.get_by_role("button", name=re.compile("Add to Cart", re.IGNORECASE))),
            "buy_now": visible(page.locator("#buy-now-button"))
            or visible(page.get_by_role("button", name=re.compile("Buy Now", re.IGNORECASE))),
            "unavailable": visible(page.get_by_text("Currently unavailable", exact=False)),
            "out_of_stock": visible(page.get_by_text("out of stock", exact=False))
            or visible(page.get_by_text("Temporarily out of stock", exact=False)),
        }

    def _get_price(self, page: Page) -> Optional[str]:
        # Amazon's visible price is usually split across sibling spans
        # (whole/fraction); the full string lives in a hidden .a-offscreen
        # span specifically so screen readers (and we) can read it in one go.
        try:
            offscreen = page.locator("span.a-price .a-offscreen").first
            if offscreen.is_visible(timeout=2000):
                return offscreen.inner_text().strip()
        except Exception:
            pass
        try:
            price_locator = page.get_by_text(PRICE_RE)
            if price_locator.first.is_visible(timeout=3000):
                return price_locator.first.inner_text().strip()
        except Exception:
            pass
        return None
