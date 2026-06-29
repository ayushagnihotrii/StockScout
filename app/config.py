"""Central configuration loaded from environment variables (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# --- Required secrets / identifiers -----------------------------------------
BOT_TOKEN: str = _require("BOT_TOKEN")
CHAT_ID: str = _require("CHAT_ID")

# --- Optional behaviour knobs -------------------------------------------------
CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "300"))
HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"

# --- Filesystem locations -----------------------------------------------------
PROFILE_DIR = Path("profile")
WATCHLIST_FILE = Path("watchlist.json")
BOT_STATE_FILE = Path("bot_state.json")
SCREENSHOT_DIR = Path("screenshots")

# --- Bot conversation knobs ----------------------------------------------------
PENDING_URL_TTL_SECONDS = 30 * 60
