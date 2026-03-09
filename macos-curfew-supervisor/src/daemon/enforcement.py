from __future__ import annotations

import logging
import subprocess

from shared.models import LoggedInUser

LOGGER = logging.getLogger(__name__)


def force_logout_user(user: LoggedInUser) -> None:
    gui_domain = f"gui/{user.uid}"
    try:
        subprocess.run(
            ["/bin/launchctl", "bootout", gui_domain],
            check=True,
            capture_output=True,
            text=True,
        )
        LOGGER.info("bootout successful for %s", user.username)
        return
    except Exception as exc:
        LOGGER.warning("launchctl bootout failed for %s: %s", user.username, exc)

    subprocess.run(["/usr/bin/pkill", "-KILL", "-u", str(user.uid)], check=False)
    LOGGER.info("pkill fallback attempted for %s", user.username)
