#!/usr/bin/env python3
"""
Cron-friendly entrypoint that reuses the main wifi.py flow.
"""
from datetime import datetime

from wifi import run_once


def log(msg: str) -> None:
    print(f"[cron_daily_reset {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def main() -> None:
    log("Starting daily Wi-Fi reset cron job...")
    try:
        run_once()
        log("✅ Wi-Fi password reset and notification sent.")
    except Exception as exc:
        log(f"❌ Failed to reset Wi-Fi password: {exc}")


if __name__ == "__main__":
    main()
