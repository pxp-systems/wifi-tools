"""
Compatibility facade so legacy imports reuse the single source of truth in wifi.py.
"""
from wifi import (  # noqa: F401
    check_for_reset_command,
    generate_password,
    run_browser_automation,
    run_once,
    send_telegram_message,
)

__all__ = [
    "check_for_reset_command",
    "generate_password",
    "run_browser_automation",
    "run_once",
    "send_telegram_message",
]
