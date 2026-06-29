# Stock Watchlist Bot

A Telegram bot that watches Flipkart and Amazon product pages and tells
you the moment something becomes available — for free, with your machine
turned off.

## How it works

1. **You register a product by chatting with your own bot**: paste a
   Flipkart or Amazon product link, then send your delivery pincode in a
   follow-up message. The bot replies with a confirmation and starts
   tracking it.
2. Every 5 minutes, a GitHub Actions workflow runs `monitor.py`, which:
   - Polls Telegram for any new messages and turns them into watchlist
     registrations (see the conversation flow below).
   - Opens each tracked product in Playwright Chromium, applies the saved
     pincode, and reads stock/price from multiple signals (Buy Now / Add
     to Cart vs. Sold Out / Unavailable / undeliverable text) — never a
     single fragile check.
   - Notifies you on Telegram only when a product's status or price
     actually changes, never on every run.
3. There is no server and no database. `watchlist.json` and
   `bot_state.json` (the Telegram offset + anything pending a pincode)
   are committed back to this repo by the workflow itself after each run
   — "git as the database." This is what lets it run for free with
   nothing on your machine.

## Conversation flow

```
You:  https://www.flipkart.com/.../p/itmXXXX
Bot:  Got the link. Now send me your pincode for this product.
You:  201301
Bot:  Got it! Tracking this flipkart product at pincode 201301.
      I'll notify you here when it's available.
```

You can also send the link and pincode in one message. Sending a link
from an unsupported store gets an explicit rejection rather than silence.
Sending a pincode with nothing pending gets told to send a link first.
A pending link expires after 30 minutes if no pincode follows.

Only messages from the `CHAT_ID` configured below are processed — anyone
else messaging the bot is ignored.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # fill in BOT_TOKEN and CHAT_ID
```

### One-time login (local only, optional)

```bash
python login.py
```

Opens a real browser window against `profile/` (gitignored) so you can
log in to Flipkart/Amazon if you want a warmer session. Neither stock
nor price reading actually requires being logged in.

### Run a single check

```bash
python monitor.py
```

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `CHAT_ID` | The only chat the bot will accept registrations from |
| `CHECK_INTERVAL` | Seconds between checks (informational; GitHub Actions uses its own cron) |
| `HEADLESS` | `true`/`false` — run Chromium headless |

Product links and pincodes are **not** environment variables anymore —
they're submitted via Telegram and stored in `watchlist.json`.

## GitHub Actions: free, always-on, by design

This repo is meant to be **public**. GitHub Actions is unlimited and free
on public repos, which is what makes 5-minute checks sustainable forever
at zero cost. The trade-off: `watchlist.json` (your tracked product links
and pincodes) is visible to anyone who finds the repo. Your bot token
never is — it stays a repository secret and is never committed.

If you'd rather keep your watchlist private, make the repo private and
widen the cron interval (e.g. every 20-30 minutes) to stay inside GitHub's
~2000 free private-Action-minutes/month — Playwright runs aren't free in
wall-clock terms.

Setup:
1. Push this repo to GitHub (public, per above).
2. Add repository secrets: `BOT_TOKEN`, `CHAT_ID`.
3. The workflow (`.github/workflows/monitor.yml`) runs every 5 minutes and
   on manual `workflow_dispatch`. After each run it commits
   `watchlist.json`/`bot_state.json` back to the repo (rebasing and
   retrying once if another run pushed in between) so the next run
   remembers everything.

On repeated per-product failures, a screenshot is uploaded as a workflow
artifact and a Telegram error is sent — one bad product never blocks the
rest of the watchlist.

## Amazon is less reliable than Flipkart

Amazon aggressively rate-limits and CAPTCHAs automated traffic, especially
from shared datacenter IPs like GitHub-hosted runners. The Amazon checker
detects captcha/block pages and degrades to `UNKNOWN` (logged, never
notified as a false stock change) rather than guessing. Expect occasional
gaps in Amazon coverage; Flipkart checks are far steadier.

## Project layout

```
app/
  stores/
    base.py      StoreChecker interface (extract_product_id, apply_pincode, get_stock_status, validate)
    flipkart.py   Flipkart PID extraction + multi-signal stock/price detection
    amazon.py     Amazon ASIN extraction + captcha-aware stock/price detection
  browser.py      BrowserSession: one persistent Chromium context per run
  telegram.py     Telegram Bot API: sendMessage/getUpdates + notify_* helpers
  telegram_bot.py Chat-based registration flow (link -> pincode -> watchlist entry)
  watchlist.py    Typed helpers over watchlist.json
  jsonstore.py    Generic JSON load/save
  config.py       Loads and validates .env
  logger.py       Shared structured logging
monitor.py        Entry point: poll Telegram -> check every entry -> notify -> save
login.py          Optional one-time local helper to warm up the persistent profile
```
