"""Telegram Bot API: sending notifications and polling for new messages."""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

import requests

from app.config import BOT_TOKEN, CHAT_ID
from app.logger import get_logger

logger = get_logger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text: str, photo_path: Optional[str] = None, chat_id: str = CHAT_ID) -> bool:
    """Send a text message, optionally attaching a screenshot. Never raises."""
    try:
        if photo_path:
            with open(photo_path, "rb") as photo:
                response = requests.post(
                    f"{TELEGRAM_API}/sendPhoto",
                    data={"chat_id": chat_id, "caption": text, "parse_mode": "HTML"},
                    files={"photo": photo},
                    timeout=30,
                )
        else:
            response = requests.post(
                f"{TELEGRAM_API}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=30,
            )
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        return False


def get_updates(offset: int) -> List[Dict[str, Any]]:
    """Short-poll new messages since `offset`. Never raises -- returns []
    on any failure so a Telegram outage doesn't break stock checking."""
    try:
        response = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params={"offset": offset, "timeout": 0},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("result", [])
    except Exception as exc:
        logger.error("Failed to fetch Telegram updates: %s", exc)
        return []


def notify_in_stock(title: str, price: Optional[str], url: str, chat_id: str = CHAT_ID) -> bool:
    price_line = f"\n\U0001f4b0 Price: <b>{html.escape(price)}</b>" if price else ""
    message = (
        "\U0001f7e2 <b>IN STOCK!</b>\n\n"
        f"{html.escape(title)}{price_line}\n"
        f"\U0001f517 {url}"
    )
    return send_message(message, chat_id=chat_id)


def notify_out_of_stock(title: str, chat_id: str = CHAT_ID) -> bool:
    message = f"\U0001f534 Now OUT OF STOCK.\n{html.escape(title)}"
    return send_message(message, chat_id=chat_id)


def notify_price_change(
    old_price: Optional[str], new_price: Optional[str], url: str, chat_id: str = CHAT_ID
) -> bool:
    message = (
        "\U0001f4b8 <b>Price changed</b>\n\n"
        f"Old: {html.escape(old_price) if old_price else 'unknown'}\n"
        f"New: {html.escape(new_price) if new_price else 'unknown'}\n"
        f"\U0001f517 {url}"
    )
    return send_message(message, chat_id=chat_id)


def notify_validation_failure(reason: str, url: str = "", chat_id: str = CHAT_ID) -> bool:
    url_line = f"\n\U0001f517 {url}" if url else ""
    message = (
        "⚠️ <b>Product page changed. Please verify manually.</b>\n\n"
        f"Reason: {html.escape(reason)}{url_line}"
    )
    return send_message(message, chat_id=chat_id)


def notify_error(reason: str, photo_path: Optional[str] = None, chat_id: str = CHAT_ID) -> bool:
    message = f"❗ Monitor error:\n{html.escape(reason)}"
    return send_message(message, photo_path=photo_path, chat_id=chat_id)
