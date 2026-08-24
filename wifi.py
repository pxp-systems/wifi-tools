#!/usr/bin/env python3
"""
wifi.py — Guest Wi-Fi password rotator + downtime scheduler + Telegram notifier (Netgear Orbi)

- Generates a password (digits-only or prefix+digits)
- Uses Playwright to log into Orbi and update Guest Network passphrase
- Turns the Guest Network off/on automatically on a downtime schedule
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
import fcntl
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Callable, Optional, Set

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
GUEST_SSID_SELECTOR = os.getenv("GUEST_SSID_SELECTOR", "#ssid")
GUEST_PASSWORD_SELECTOR = os.getenv("GUEST_PASSWORD_SELECTOR", "#passphrase")
SAVE_BUTTON_SELECTOR = os.getenv("SAVE_BUTTON_SELECTOR", 'button:has-text("Apply")')

# "Enable Guest Network" checkbox — used by the downtime scheduler.
# Confirm this one with `playwright codegen` against your own firmware.
GUEST_ENABLE_SELECTOR = os.getenv("GUEST_ENABLE_SELECTOR", "#enable_guest")

# If Orbi UI is inside an iframe (your codegen shows #page)
GUEST_IFRAME_SELECTOR = os.getenv("GUEST_IFRAME_SELECTOR", "#page")

# How long to sit on the page after Apply (Orbi restarts the guest radio)
GUEST_APPLY_WAIT_MS = int(os.getenv("GUEST_APPLY_WAIT_MS", "60000"))

HEADLESS = os.getenv("HEADLESS", "true").lower() in {"1", "true", "yes"}

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]

# State directory and update id tracking
STATE_DIR = Path(os.getenv("STATE_DIR", os.path.expanduser("~/.wifi-automation")))
LAST_UPDATE_ID_FILE = Path(
    os.path.expanduser(os.getenv("LAST_UPDATE_ID_FILE", str(STATE_DIR / "last_telegram_update")))
)
WATCH_LOCK_FILE = Path(os.getenv("WATCH_LOCK_FILE", "/tmp/wifi-automation-reset.lock"))

_WATCH_LOCK_HANDLE = None

# Password policy
PASSWORD_MODE = os.getenv("PASSWORD_MODE", "digits")  # digits | prefix+digits
PASSWORD_LETTERS = os.getenv("PASSWORD_LETTERS", "asdfgwertcv")
PASSWORD_PREFIX_LEN = int(os.getenv("PASSWORD_PREFIX_LEN", "3"))
PASSWORD_DIGIT_LEN = int(os.getenv("PASSWORD_DIGIT_LEN", "5"))
PASSWORD_DIGITS_ONLY_LEN = int(os.getenv("PASSWORD_DIGITS_ONLY_LEN", "5"))

# Reset command cooldown
RESET_COOLDOWN_SECONDS = int(os.getenv("RESET_COOLDOWN_SECONDS", "60"))

# Downtime schedule (local time). While inside the window the guest network is
# switched off; outside it, back on.
DOWNTIME_ENABLED = os.getenv("DOWNTIME_ENABLED", "false").lower() in {"1", "true", "yes"}
DOWNTIME_START = os.getenv("DOWNTIME_START", "22:30")
DOWNTIME_END = os.getenv("DOWNTIME_END", "06:30")
# all | weekdays | weekends | comma-separated day names (mon,tue,...)
DOWNTIME_DAYS = os.getenv("DOWNTIME_DAYS", "all")
DOWNTIME_NOTIFY = os.getenv("DOWNTIME_NOTIFY", "true").lower() in {"1", "true", "yes"}
GUEST_STATE_FILE = Path(
    os.path.expanduser(os.getenv("GUEST_STATE_FILE", str(STATE_DIR / "guest_state")))
)

_DAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _require_env(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def send_telegram_text(text: str) -> None:
    token = _require_env("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not TELEGRAM_CHAT_IDS:
        raise RuntimeError("Missing TELEGRAM_CHAT_IDS (comma-separated).")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for chat_id in TELEGRAM_CHAT_IDS:
        data = {"chat_id": chat_id, "text": text}
        try:
            r = requests.post(url, data=data, timeout=20)
            if r.status_code == 200:
                print(f"✅ Telegram sent to {chat_id}")
            else:
                print(f"❌ Telegram failed for {chat_id}: {r.text}")
        except Exception as e:
            print(f"❌ Telegram error for {chat_id}: {e}")


def send_telegram_message(password: str) -> None:
    message = f"🔐 Guest Wi-Fi password for {datetime.now().strftime('%A %d %B')}:\n\n{password}"
    send_telegram_text(message)


def generate_password() -> str:
    if PASSWORD_MODE == "digits":
        return "".join(random.choices(string.digits, k=PASSWORD_DIGITS_ONLY_LEN))

    prefix = "".join(random.choices(PASSWORD_LETTERS, k=PASSWORD_PREFIX_LEN))
    digits = "".join(random.choices(string.digits, k=PASSWORD_DIGIT_LEN))
    return prefix + digits


def generate_network_name() -> str:
    return datetime.now().strftime("AG-%d%m%y%H%M")


# -----------------------------
# Downtime schedule
# -----------------------------


def parse_hhmm(value: str) -> dtime:
    match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", value or "")
    if not match:
        raise ValueError(f"Invalid time (expected HH:MM): {value!r}")

    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"Invalid time (expected HH:MM): {value!r}")

    return dtime(hour, minute)


def parse_days(value: str) -> Set[int]:
    """Return weekday numbers (Mon=0) the downtime window may start on."""
    raw = (value or "").strip().lower()
    if raw in {"", "all", "daily", "everyday", "every day"}:
        return set(range(7))
    if raw in {"weekdays", "weekday"}:
        return {0, 1, 2, 3, 4}
    if raw in {"weekends", "weekend"}:
        return {5, 6}

    days = set()
    for token in raw.replace(" ", "").split(","):
        if not token:
            continue
        key = token[:3]
        if key not in _DAY_NAMES:
            raise ValueError(f"Unknown day in DOWNTIME_DAYS: {token!r}")
        days.add(_DAY_NAMES[key])

    if not days:
        raise ValueError(f"No usable days in DOWNTIME_DAYS: {value!r}")
    return days


def is_downtime(
    now: Optional[datetime] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    days: Optional[str] = None,
) -> bool:
    """True when `now` falls inside the configured downtime window."""
    now = now or datetime.now()
    start_t = parse_hhmm(DOWNTIME_START if start is None else start)
    end_t = parse_hhmm(DOWNTIME_END if end is None else end)
    active_days = parse_days(DOWNTIME_DAYS if days is None else days)

    if start_t == end_t:
        # Zero-length window: never down (use DOWNTIME_ENABLED=false instead).
        return False

    current = now.time()

    if start_t < end_t:
        # Same-day window, keyed on today's weekday.
        return now.weekday() in active_days and start_t <= current < end_t

    # Window crosses midnight.
    if current >= start_t:
        return now.weekday() in active_days
    if current < end_t:
        # Still inside a window that started yesterday.
        return (now - timedelta(days=1)).weekday() in active_days
    return False


def desired_guest_state(now: Optional[datetime] = None) -> bool:
    """Guest network state the schedule wants right now (True = on)."""
    return not is_downtime(now)


def load_guest_state() -> Optional[bool]:
    try:
        if GUEST_STATE_FILE.exists():
            with open(GUEST_STATE_FILE, "r") as f:
                value = (f.read() or "").strip().lower()
            if value == "on":
                return True
            if value == "off":
                return False
    except Exception:
        pass
    return None


def save_guest_state(enabled: bool) -> None:
    try:
        GUEST_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        with open(GUEST_STATE_FILE, "w") as f:
            f.write("on" if enabled else "off")
    except Exception:
        pass


def describe_schedule() -> str:
    if not DOWNTIME_ENABLED:
        return "downtime disabled"
    return f"downtime {DOWNTIME_START}–{DOWNTIME_END} ({DOWNTIME_DAYS})"


def apply_schedule(force: bool = False) -> Optional[bool]:
    """
    Bring the guest network in line with the downtime schedule.

    Returns the state now believed to be applied (True = on), or None when the
    schedule is disabled or the router update failed.
    """
    if not DOWNTIME_ENABLED:
        return None

    wanted = desired_guest_state()
    known = load_guest_state()

    if not force and known == wanted:
        return wanted

    label = "on" if wanted else "off"
    print(f"🕒 Schedule: switching guest network {label} ({describe_schedule()})")

    if not set_guest_network_enabled(wanted):
        # Leave the state file alone so the next tick retries.
        return None

    save_guest_state(wanted)

    if DOWNTIME_NOTIFY and known != wanted:
        try:
            send_telegram_text(_downtime_message(wanted))
        except Exception as e:
            print(f"❌ Downtime notification failed: {e}")

    return wanted


def _downtime_message(enabled: bool) -> str:
    if enabled:
        return f"☀️ Guest Wi-Fi is back ON (downtime ended {DOWNTIME_END})."
    return f"🌙 Guest Wi-Fi is OFF for downtime until {DOWNTIME_END}."


# -----------------------------
# Browser automation
# -----------------------------


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


def _guest_session(action: Callable[[object], None], label: str) -> bool:
    """
    Log into the router, open the Guest Network page and run `action(frame)`.
    Returns True when the action completed without raising.
    """
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

            # Guest network settings live inside an iframe on Orbi
            frame = page.frame_locator(GUEST_IFRAME_SELECTOR)
            action(frame)

            page.wait_for_timeout(GUEST_APPLY_WAIT_MS)

            context.close()
            browser.close()
            return True

    except Exception as e:
        try:
            if page is not None:
                slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
                screenshot_path = f"fail-{slug}.png"
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"🖼️ Saved {screenshot_path}")
        except Exception:
            pass

        print(f"❌ Error during {label}:", e)

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


def run_browser_automation(new_password: str, new_ssid: Optional[str] = None) -> bool:
    if new_ssid is None:
        new_ssid = generate_network_name()

    return _guest_session(
        lambda frame: _update_guest_network(frame, new_password, new_ssid),
        "password update",
    )


def set_guest_network_enabled(enabled: bool) -> bool:
    """Turn the guest network on or off via the router UI."""
    return _guest_session(
        lambda frame: _set_guest_network_enabled(frame, enabled),
        "guest network on" if enabled else "guest network off",
    )


def _update_guest_network(frame, new_password: str, new_ssid: str) -> None:
    ssid_locator = frame.locator(GUEST_SSID_SELECTOR)
    ssid_locator.wait_for(timeout=30000)
    _select_all_and_overtype(ssid_locator, new_ssid)

    password_locator = frame.locator(GUEST_PASSWORD_SELECTOR)
    password_locator.wait_for(timeout=30000)
    _select_all_and_overtype(password_locator, new_password)
    frame.locator(SAVE_BUTTON_SELECTOR).click(timeout=120000)


def _set_guest_network_enabled(frame, enabled: bool) -> None:
    toggle = frame.locator(GUEST_ENABLE_SELECTOR)
    toggle.wait_for(timeout=30000)

    if _toggle_is_on(toggle) == enabled:
        print(f"ℹ️ Guest network already {'on' if enabled else 'off'} — nothing to apply")
        return

    _set_toggle(toggle, enabled)
    frame.locator(SAVE_BUTTON_SELECTOR).click(timeout=120000)


def _toggle_is_on(locator) -> Optional[bool]:
    """Best-effort read of a checkbox / switch. None when it can't be determined."""
    try:
        return locator.is_checked()
    except Exception:
        pass

    try:
        aria = locator.get_attribute("aria-checked")
        if aria is not None:
            return aria.strip().lower() == "true"
    except Exception:
        pass

    return None


def _set_toggle(locator, enabled: bool) -> None:
    try:
        if enabled:
            locator.check(timeout=10000)
        else:
            locator.uncheck(timeout=10000)
    except Exception:
        # Non-standard switch widget: fall back to a plain click.
        locator.click(timeout=10000)


def _select_all_and_overtype(locator, value: str) -> None:
    locator.click(timeout=10000)
    locator.press("ControlOrMeta+a")
    locator.type(value)
    # Some router UIs under headless/Xvfb occasionally ignore Ctrl/Cmd+A.
    # Verify the typed value and force fill if needed.
    try:
        if locator.input_value() != value:
            locator.fill(value)
    except Exception:
        locator.fill(value)


def _acquire_watch_lock() -> None:
    global _WATCH_LOCK_HANDLE
    WATCH_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = open(WATCH_LOCK_FILE, "w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError(f"Another reset watcher is already running (lock: {WATCH_LOCK_FILE})")

    handle.seek(0)
    handle.truncate(0)
    handle.write(str(os.getpid()))
    handle.flush()
    _WATCH_LOCK_HANDLE = handle


def run_once() -> None:
    new_password = generate_password()
    new_ssid = generate_network_name()
    success = run_browser_automation(new_password, new_ssid)
    if success:
        send_telegram_message(new_password)


def load_last_update_id() -> int:
    try:
        if LAST_UPDATE_ID_FILE.exists():
            with open(LAST_UPDATE_ID_FILE, "r") as f:
                return int((f.read() or "0").strip())
    except Exception:
        pass
    return 0


def save_last_update_id(update_id: int) -> None:
    try:
        LAST_UPDATE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        with open(LAST_UPDATE_ID_FILE, "w") as f:
            f.write(str(update_id))
    except Exception:
        pass


def check_for_reset_command() -> None:
    _acquire_watch_lock()

    token = _require_env("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    allowed_chat_ids = set(TELEGRAM_CHAT_IDS)
    if not allowed_chat_ids:
        raise RuntimeError("Missing TELEGRAM_CHAT_IDS (comma-separated).")

    base_url = f"https://api.telegram.org/bot{token}/getUpdates"
    last_update_id = load_last_update_id()
    last_reset_time = 0.0

    print(f"📡 Watching Telegram for /reset ... (state: {LAST_UPDATE_ID_FILE}, chats: {allowed_chat_ids})")
    print(f"🕒 Schedule: {describe_schedule()}")

    while True:
        try:
            apply_schedule()
        except Exception as e:
            print("❌ Downtime schedule error:", e)

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
                        ssid = generate_network_name()
                        if run_browser_automation(pw, ssid):
                            send_telegram_message(pw)
                            last_reset_time = now
                    else:
                        remaining = int(RESET_COOLDOWN_SECONDS - (now - last_reset_time))
                        print(f"⏳ Reset skipped: {remaining}s cooldown remaining")

                last_update_id = update_id
                save_last_update_id(last_update_id)

        except Exception as e:
            print("❌ Telegram polling error:", e)


def _cli_set_guest(enabled: bool) -> None:
    if set_guest_network_enabled(enabled):
        save_guest_state(enabled)
        print(f"✅ Guest network {'on' if enabled else 'off'}")
    else:
        print(f"❌ Failed to turn guest network {'on' if enabled else 'off'}")
        sys.exit(1)


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--watch" in args:
        check_for_reset_command()
    elif "--guest-off" in args:
        _cli_set_guest(False)
    elif "--guest-on" in args:
        _cli_set_guest(True)
    elif "--apply-schedule" in args:
        if not DOWNTIME_ENABLED:
            print("ℹ️ DOWNTIME_ENABLED is false — nothing to do")
        else:
            apply_schedule(force="--force" in args)
    else:
        run_once()
