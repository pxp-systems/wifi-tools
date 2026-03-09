from __future__ import annotations

import subprocess


def show_notification(title: str, message: str) -> None:
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["/usr/bin/osascript", "-e", script], check=False)
