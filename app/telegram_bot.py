"""Telegram chat-based registration flow: paste a link, then a pincode.

Each run short-polls getUpdates() once (no long-running daemon) and turns
new messages into watchlist registrations. Only messages from the
configured CHAT_ID are processed -- this is a personal bot, not a public
one.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import CHAT_ID, PENDING_URL_TTL_SECONDS
from app.logger import get_logger
from app.stores import detect_store
from app.telegram import get_updates, send_message
from app.watchlist import find_entry, make_id, new_entry

logger = get_logger(__name__)

URL_RE = re.compile(r"https?://\S+")
INLINE_PINCODE_RE = re.compile(r"(?<!\d)\d{6}(?!\d)")


def process_telegram_messages(bot_state: Dict[str, Any], watchlist: List[dict]) -> None:
    """Mutates `bot_state` and `watchlist` in place based on new messages."""
    offset = bot_state.get("last_update_id", 0) + 1
    updates = get_updates(offset)

    for update in updates:
        bot_state["last_update_id"] = update["update_id"]

        message = update.get("message")
        if not message or "text" not in message:
            continue

        chat_id = str(message["chat"]["id"])
        if chat_id != CHAT_ID:
            logger.warning("Ignoring message from unrecognized chat_id %s", chat_id)
            continue

        _handle_message(bot_state, watchlist, chat_id, message["text"])


def _handle_message(bot_state: Dict[str, Any], watchlist: List[dict], chat_id: str, text: str) -> None:
    url_match = URL_RE.search(text)
    bare_pincode = _bare_pincode(text)

    if url_match:
        url = url_match.group(0)
        detection = detect_store(url)
        if detection is None:
            send_message(
                "⚠️ Unsupported store link. I can only track Flipkart and Amazon product links.",
                chat_id=chat_id,
            )
            return

        store, product_id = detection

        # Same message also contains a pincode -> register immediately.
        inline_pincode = INLINE_PINCODE_RE.search(text.replace(url, ""))
        if inline_pincode:
            reply = _register_or_update(watchlist, store, url, product_id, inline_pincode.group(0), chat_id)
            bot_state["pending_url"] = None
            send_message(reply, chat_id=chat_id)
            return

        had_pending = bot_state.get("pending_url") is not None
        bot_state["pending_url"] = {
            "url": url,
            "store": store,
            "product_id": product_id,
            "chat_id": chat_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        prefix = "Replacing your previous pending link. " if had_pending else ""
        send_message(f"{prefix}Got the link. Now send me your pincode for this product.", chat_id=chat_id)
        return

    if bare_pincode:
        pending = bot_state.get("pending_url")
        if pending and pending["chat_id"] == chat_id and not _is_expired(pending):
            reply = _register_or_update(
                watchlist, pending["store"], pending["url"], pending["product_id"], bare_pincode, chat_id
            )
            bot_state["pending_url"] = None
            send_message(reply, chat_id=chat_id)
        else:
            bot_state["pending_url"] = None
            send_message("Send a product link first, then your pincode.", chat_id=chat_id)
        return

    send_message(
        "Send me a Flipkart or Amazon product link, then your pincode, and I'll track it for you.",
        chat_id=chat_id,
    )


def _bare_pincode(text: str) -> Optional[str]:
    stripped = text.strip()
    return stripped if re.fullmatch(r"\d{6}", stripped) else None


def _is_expired(pending: Dict[str, Any]) -> bool:
    try:
        received = datetime.fromisoformat(pending["received_at"])
    except Exception:
        return True
    age = (datetime.now(timezone.utc) - received).total_seconds()
    return age > PENDING_URL_TTL_SECONDS


def _register_or_update(
    watchlist: List[dict], store: str, url: str, product_id: str, pincode: str, chat_id: str
) -> str:
    entry_id = make_id(store, product_id)
    existing = find_entry(watchlist, entry_id)
    if existing:
        existing["pincode"] = pincode
        existing["url"] = url
        return f"Already tracking this {store} product — updated pincode to {pincode}."

    watchlist.append(new_entry(store, url, product_id, pincode, chat_id))
    return (
        f"Got it! Tracking this {store} product at pincode {pincode}. "
        "I'll notify you here when it's available."
    )
