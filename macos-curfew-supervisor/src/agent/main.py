from __future__ import annotations

import argparse
import getpass
import json
import logging
import time
from pathlib import Path

from agent.browser_launcher import open_warning_url
from agent.notifications import show_notification
from daemon.config import load_config
from daemon.session_manager import is_admin_user

LOGGER = logging.getLogger(__name__)


def _consume_warnings(drop_dir: Path, username: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if not drop_dir.exists():
        return events

    for path in sorted(drop_dir.glob(f"{username}-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            events.append(payload)
        finally:
            path.unlink(missing_ok=True)
    return events


def run_loop(config_path: str) -> None:
    cfg = load_config(config_path)
    username = getpass.getuser()

    if is_admin_user(username):
        LOGGER.info("Agent inert for admin user %s", username)
        while True:
            time.sleep(60)

    while True:
        for event in _consume_warnings(cfg.warning_drop_dir, username=username):
            token = event.get("token", "")
            deadline = event.get("deadline", "")
            url = f"http://{cfg.web_host}:{cfg.web_port}/warning?token={token}"
            show_notification(
                "Curfew warning",
                f"This account will be logged out at {deadline}. Enter override code if needed.",
            )
            open_warning_url(url)
        time.sleep(3)


def main() -> None:
    parser = argparse.ArgumentParser(description="macOS Curfew Supervisor agent")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_loop(args.config)


if __name__ == "__main__":
    main()
