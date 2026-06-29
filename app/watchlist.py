"""Typed helpers over watchlist.json -- the list of products being tracked."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, TypedDict

from app.config import WATCHLIST_FILE
from app.jsonstore import load_json, save_json


class WatchlistEntry(TypedDict):
    id: str  # f"{store}:{product_id}"
    store: str  # "flipkart" / "amazon"
    url: str
    product_id: str
    pincode: str
    chat_id: str
    title: str
    status: str  # IN_STOCK / OUT_OF_STOCK / UNKNOWN
    price: Optional[str]
    pincode_applied: Optional[bool]
    added_at: str
    last_checked: str


def make_id(store: str, product_id: str) -> str:
    return f"{store}:{product_id}"


def load_watchlist() -> List[WatchlistEntry]:
    return load_json(WATCHLIST_FILE, [])


def save_watchlist(entries: List[WatchlistEntry]) -> None:
    save_json(WATCHLIST_FILE, entries)


def find_entry(entries: List[WatchlistEntry], entry_id: str) -> Optional[WatchlistEntry]:
    for entry in entries:
        if entry["id"] == entry_id:
            return entry
    return None


def new_entry(store: str, url: str, product_id: str, pincode: str, chat_id: str) -> WatchlistEntry:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": make_id(store, product_id),
        "store": store,
        "url": url,
        "product_id": product_id,
        "pincode": pincode,
        "chat_id": chat_id,
        "title": "",
        "status": "UNKNOWN",
        "price": None,
        "pincode_applied": None,
        "added_at": now,
        "last_checked": "",
    }
