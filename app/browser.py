"""Owns one persistent Chromium context for an entire monitor run.

Using launch_persistent_context() keeps cookies and any logged-in session
in `profile/` across runs (see login.py for the one-time manual login).
The context is launched once per run and reused across every watchlist
entry -- each entry gets its own fresh Page so leftover modal/popup state
from one product can never bleed into the next.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import BrowserContext, Page, sync_playwright

from app.config import HEADLESS, PROFILE_DIR
from app.logger import get_logger

logger = get_logger(__name__)


class BrowserSession:
    """Context-manager wrapper around a persistent Chromium session."""

    def __init__(self) -> None:
        self._playwright = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self) -> "BrowserSession":
        self._playwright = sync_playwright().start()
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=HEADLESS,
            viewport={"width": 1440, "height": 900},
            locale="en-IN",
        )
        self._context.set_default_timeout(30000)
        return self

    def open(self, url: str) -> Page:
        """Open a fresh page navigated to `url`."""
        page = self._context.new_page()
        logger.info("Opening: %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        return page

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()
