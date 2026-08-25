"""
Compatibility facade so legacy imports reuse the single source of truth in wifi.py.
"""
from wifi import (  # noqa: F401
    apply_schedule,
    check_for_reset_command,
    desired_guest_state,
    generate_password,
    is_downtime,
    run_browser_automation,
    run_once,
    send_telegram_message,
    set_guest_network_enabled,
)

__all__ = [
    "apply_schedule",
    "check_for_reset_command",
    "desired_guest_state",
    "generate_password",
    "is_downtime",
    "run_browser_automation",
    "run_once",
    "send_telegram_message",
    "set_guest_network_enabled",
]
