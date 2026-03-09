from __future__ import annotations

import subprocess


def open_warning_url(url: str) -> None:
    subprocess.run(["/usr/bin/open", url], check=False)
