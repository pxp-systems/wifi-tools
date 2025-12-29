#!/usr/bin/env python3
"""
wifi.py — Guest Wi-Fi password rotator + Telegram notifier (Netgear Orbi)

- Generates a password (digits-only or prefix+digits)
- Uses Playwright to log into Orbi and update Guest Network passphrase
- Sends the new password to Telegram
- Optional: polls Telegram for /reset (cooldown enforced)

Python 3.9 compatible.
"""

import os
import sys
import time
import random
import string
import re
from datetime import datetime
from typing import Optional

import requests
from playwright.sync_api import sync_playwright

# Optional .env support (safe if python-dotenv not installed)
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# -----------------------------
# Config (env-driven)
# -----------------------------

# Router
ROUTER_URL = os.getenv("ROUTER_URL", "https://orbilogin.com")
ROUTER_USERNAME = os.getenv("ROUTER_USERNAME", "")  # e.g. admin
ROUTER_ADMIN_PASSWORD = os.getenv("ROUTER_PASSWORD")  # required

# Selectors (from your Playwright codegen)
LOGIN_USERNAME_SELECTOR = os.getenv("LOGIN_USERNAME_SELECTOR", "#username")
LOGIN_PASSWORD_SELECTOR = os.getenv("LOGIN_PASSWORD_SELECTOR", "#sysPasswd")
LOGIN_BUTTON_SELECTOR = os.getenv("LOGIN_BUTTON_SELECTOR", 'button:has-text("Login")')

GUEST_MENU_SELECTOR = os.getenv("GUEST_MENU_SELECTOR", 'a:has-text("Guest Network")')
GUEST_PASSWORD_SELECTOR = os.getenv("GUEST_PASSWORD_SELECTOR", "#passphrase")
SAVE_BUTTON_SELECTOR = os.getenv("SAVE_BUTTON_SELECTOR", 'button:has-text("Apply")')

# If Orbi UI is inside an iframe (your codegen shows #page)
GUEST_IFRAME_SELECTOR = os.getenv("GUEST_IFRAME_SELECTOR", "#page")

HEADLESS = os.getenv("HEADLESS", "true").lower() in {"1", "true", "yes"}

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]

# Where we persist the last Telegram update id
LAST_UPDATE_ID_FILE = os.getenv("LAST_UPDATE_ID_FILE", "/home/admin/.last_telegram_update")

# Password policy
PASSWORD_MODE = os.getenv("PASSWORD_MODE", "digits")  # digits | prefix+digits
PASSWORD_LETTERS = os.getenv("PASSWORD_LETTERS", "asdfgwertcv")
PASSWORD_PREFIX_LEN = int(os.getenv("PASSWORD_PREFIX_LEN", "3"))
PASSWORD_DIGIT_LEN = int(os.getenv("PASSWORD_DIGIT_LEN", "5"))
PASSWORD_DIGITS_ONLY_LEN = int(os.getenv("PASSWORD_DIGITS_ONLY_LEN", "5"))

# Reset command cooldown
RESET_COOLDOWN_SECONDS = int(os.getenv("RESET_COOLDOWN_SECONDS", "60"))


def _require_env(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def send_telegram_message(password: str) -> None:
    token = _require_env("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not TELEGRAM_CHAT_IDS:
        raise RuntimeError("Missing TELEGRAM_CHAT_IDS (comma-separated).")

    message = f"🔐 Guest Wi-Fi password for {datetime.now().strftime('%A %d %B')}:\n\n{password}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for chat_id in TELEGRAM_CHAT_IDS:
        data = {"chat_id": chat_id, "text": message}
        try:
            r = requests.post(url, data=data, timeout=20)
            if r.status_code == 200:
                print(f"✅ Telegram sent to {chat_id}")
            else:
                print(f"❌ Telegram failed for {chat_id}: {r.text}")
        except Exception as e:
            print(f"❌ Telegram error for {chat_id}: {e}")


def generate_password() -> str:
    if PASSWORD_MODE == "digits":
        return "".join(random.choices(string.digits, k=PASSWORD_DIGITS_ONLY_LEN))

    prefix = "".join(random.choices(PASSWORD_LETTERS, k=PASSWORD_PREFIX_LEN))
    digits = "".join(random.choices(string.digits, k=PASSWORD_DIGIT_LEN))
    return prefix + digits


def _accept_tls_interstitial(page) -> None:
    """
    Click through Chromium 'Your connection is not private' interstitial.
    Matches the path you recorded: Advanced -> Proceed.
    """
    try:
        # Prefer stable IDs if present
        if page.locator("#details-button").count() > 0:
            page.locator("#details-button").click(timeout=5000)
            page.wait_for_timeout(300)
        else:
            page.get_by_role("button", name="Advanced").click(timeout=5000)
            page.wait_for_timeout(300)

        if page.locator("#proceed-link").count() > 0:
            page.locator("#proceed-link").click(timeout=5000)
        else:
            page.get_by_role(
                "link",
                name=re.compile(r"Proceed to .*orbilogin\.com", re.I)
            ).click(timeout=5000)

        # Let UI load
        try:
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception:
            pass
    except Exception:
        # Not on interstitial, or couldn't click it — ignore.
        pass


def run_browser_automation(new_password: str) -> bool:
    admin_password = _require_env("ROUTER_PASSWORD", ROUTER_ADMIN_PASSWORD)

    browser = None
    context = None
    page = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context()
            page = context.new_page()

            # Navigate (Playwright may throw on CERT_AUTHORITY_INVALID; continue anyway)
            try:
                page.goto(ROUTER_URL, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                 # Only continue if it's the cert interstitial case
                 msg = str(e)
                 print(f"❌ goto failed: {msg}")
                 if "ERR_CERT_AUTHORITY_INVALID" not in msg:
                   raise

            _accept_tls_interstitial(page)

            # Let things settle a bit (Orbi UI can be slow)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass

            # Login
            if LOGIN_USERNAME_SELECTOR and ROUTER_USERNAME:
                page.wait_for_selector(LOGIN_USERNAME_SELECTOR, timeout=60000, state="attached")
                page.fill(LOGIN_USERNAME_SELECTOR, ROUTER_USERNAME)

            page.wait_for_selector(LOGIN_PASSWORD_SELECTOR, timeout=60000, state="attached")
            page.fill(LOGIN_PASSWORD_SELECTOR, admin_password)

            # Some firmwares want click, some accept Enter
            try:
                page.click(LOGIN_BUTTON_SELECTOR, timeout=8000)
            except Exception:
                try:
                    page.press(LOGIN_PASSWORD_SELECTOR, "Enter")
                except Exception:
                    pass

            page.wait_for_timeout(1500)

            # Navigate to Guest Network
            page.locator(GUEST_MENU_SELECTOR).first.click(timeout=30000)
            page.wait_for_timeout(1500)

            # Update guest password (inside iframe on Orbi)
            frame = page.frame_locator(GUEST_IFRAME_SELECTOR)
            frame.locator(GUEST_PASSWORD_SELECTOR).wait_for(timeout=30000)
            frame.locator(GUEST_PASSWORD_SELECTOR).fill(new_password)
            frame.locator(SAVE_BUTTON_SELECTOR).click(timeout=120000)

            page.wait_for_timeout(60000)

            context.close()
            browser.close()
            return True

    except Exception as e:
        try:
            if page is not None:
                page.screenshot(path="fail.png", full_page=True)
                print("🖼️ Saved fail.png")
        except Exception:
            pass

        print("❌ Error during password update:", e)

        try:
            if context is not None:
                context.close()
        except Exception:
            pass

        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

        return False


def run_once() -> None:
    new_password = generate_password()
    success = run_browser_automation(new_password)
    if success:
        send_telegram_message(new_password)


def load_last_update_id() -> int:
    try:
        if os.path.exists(LAST_UPDATE_ID_FILE):
            with open(LAST_UPDATE_ID_FILE, "r") as f:
                return int((f.read() or "0").strip())
    except Exception:
        pass
    return 0


def save_last_update_id(update_id: int) -> None:
    try:
        parent = os.path.dirname(LAST_UPDATE_ID_FILE)
        if parent:
            os.makedirs(parent, exist_ok=True)
    except Exception:
        pass

    try:
        with open(LAST_UPDATE_ID_FILE, "w") as f:
            f.write(str(update_id))
    except Exception:
        pass


def check_for_reset_command() -> None:
    token = _require_env("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    allowed_chat_ids = set(TELEGRAM_CHAT_IDS)
    if not allowed_chat_ids:
        raise RuntimeError("Missing TELEGRAM_CHAT_IDS (comma-separated).")

    base_url = f"https://api.telegram.org/bot{token}/getUpdates"
    last_update_id = load_last_update_id()
    last_reset_time = 0.0

    print("📡 Watching Telegram for /reset ...")

    while True:
        try:
            params = {"offset": last_update_id + 1, "timeout": 30}
            r = requests.get(base_url, params=params, timeout=35)
            data = r.json()
            updates = data.get("result", [])

            for update in updates:
                update_id = update.get("update_id")
                message = update.get("message", {}) or {}
                text = (message.get("text", "") or "").strip().lower()
                chat_id = str((message.get("chat", {}) or {}).get("id", ""))

                if update_id is None or update_id <= last_update_id:
                    continue

                if chat_id in allowed_chat_ids and text == "/reset":
                    now = time.time()
                    if now - last_reset_time >= RESET_COOLDOWN_SECONDS:
                        pw = generate_password()
                        if run_browser_automation(pw):
                            send_telegram_message(pw)
                            last_reset_time = now
                    else:
                        remaining = int(RESET_COOLDOWN_SECONDS - (now - last_reset_time))
                        print(f"⏳ Reset skipped: {remaining}s cooldown remaining")

                last_update_id = update_id
                save_last_update_id(last_update_id)

        except Exception as e:
            print("❌ Telegram polling error:", e)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        check_for_reset_command()
    else:
        run_once()