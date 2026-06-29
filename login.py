"""One-time local helper: open the persistent profile and let a human log in
to Flipkart and save a delivery address. Run this once before relying on
monitor.py so the session/cookies live in profile/ and future runs never
need to log in again.
"""
from playwright.sync_api import sync_playwright

from app.config import PROFILE_DIR

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
    )

    page = context.new_page()
    page.goto("https://www.flipkart.com")

    print("Login to Flipkart if required.")
    print("Select your delivery address.")
    print("When finished, close the browser window.")

    page.wait_for_event("close")

    context.close()
