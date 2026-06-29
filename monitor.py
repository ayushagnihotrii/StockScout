"""Entry point: poll Telegram for new product registrations, then check
every watchlisted product's stock/price and notify on change. Designed to
be invoked once per run (e.g. every 5 minutes from GitHub Actions).
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import Optional

from app.browser import BrowserSession
from app.config import BOT_STATE_FILE, SCREENSHOT_DIR
from app.jsonstore import load_json, save_json
from app.logger import get_logger
from app.stores import get_checker
from app.stores.base import StockResult
from app.telegram import notify_error, notify_in_stock, notify_out_of_stock, notify_price_change, notify_validation_failure
from app.telegram_bot import process_telegram_messages
from app.watchlist import WatchlistEntry, load_watchlist, save_watchlist

logger = get_logger(__name__)

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 8


def run_once() -> None:
    bot_state = load_json(BOT_STATE_FILE, {"last_update_id": 0, "pending_url": None})
    watchlist = load_watchlist()

    try:
        process_telegram_messages(bot_state, watchlist)
    except Exception:
        logger.exception("Error while processing Telegram messages")

    if watchlist:
        with BrowserSession() as session:
            for entry in watchlist:
                try:
                    _check_entry(session, entry)
                except Exception:
                    logger.exception("[%s] unhandled error while checking entry", entry["id"])
    else:
        logger.info("Watchlist is empty; nothing to check this run")

    save_json(BOT_STATE_FILE, bot_state)
    save_watchlist(watchlist)


def _check_entry(session: BrowserSession, entry: WatchlistEntry) -> None:
    checker = get_checker(entry["store"])
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        page = None
        try:
            page = session.open(entry["url"])

            validation = checker.validate(page, entry["product_id"])
            if not validation.ok:
                logger.error("[%s] Validation failed: %s", entry["id"], validation.reason)
                notify_validation_failure(validation.reason, entry["url"], entry["chat_id"])
                entry["last_checked"] = _now()
                return

            pincode_applied = checker.apply_pincode(page, entry["pincode"])
            entry["pincode_applied"] = pincode_applied
            result = checker.get_stock_status(page, pincode_applied)
            logger.info("[%s] status=%s price=%s", entry["id"], result.status, result.price)

            _handle_entry_change(entry, result)
            entry["last_checked"] = _now()
            return

        except Exception as exc:
            last_error = exc
            logger.warning("[%s] attempt %d/%d failed: %s", entry["id"], attempt, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES:
                screenshot_path = _save_screenshot(page, entry["id"])
                notify_error(
                    f"Repeated failure checking {entry['id']}: {exc}",
                    photo_path=screenshot_path,
                    chat_id=entry["chat_id"],
                )
            else:
                time.sleep(RETRY_DELAY_SECONDS)
        finally:
            if page:
                page.close()

    logger.error("[%s] all retries exhausted: %s", entry["id"], last_error)
    entry["last_checked"] = _now()


def _handle_entry_change(entry: WatchlistEntry, result: StockResult) -> None:
    status_changed = result.status != entry.get("status")
    price_changed = (
        result.price is not None
        and entry.get("price") is not None
        and result.price != entry.get("price")
    )

    if status_changed and result.status == "IN_STOCK":
        notify_in_stock(result.title, result.price, entry["url"], entry["chat_id"])
    elif status_changed and result.status == "OUT_OF_STOCK":
        notify_out_of_stock(result.title, entry["chat_id"])

    if price_changed:
        notify_price_change(entry.get("price"), result.price, entry["url"], entry["chat_id"])

    entry["title"] = result.title or entry.get("title", "")
    entry["status"] = result.status
    entry["price"] = result.price if result.price is not None else entry.get("price")


def _save_screenshot(page, entry_id: str) -> Optional[str]:
    if not page:
        return None
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_id = entry_id.replace(":", "_")
        path = SCREENSHOT_DIR / f"failure_{safe_id}_{timestamp}.png"
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception as exc:
        logger.error("Could not capture failure screenshot: %s", exc)
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    try:
        run_once()
    except Exception as exc:
        logger.exception("Unhandled error in monitor run")
        notify_error(f"Unhandled exception: {exc}")
        sys.exit(1)
