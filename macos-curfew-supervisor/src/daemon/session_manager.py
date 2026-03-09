from __future__ import annotations

import pwd
import subprocess
from typing import Iterable

from shared.models import LoggedInUser


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return (proc.stdout or "").strip()


def is_admin_user(username: str) -> bool:
    out = _run(["/usr/bin/dsmemberutil", "checkmembership", "-U", username, "-G", "admin"])
    return "is a member" in out


def list_console_users() -> list[LoggedInUser]:
    out = _run(["/usr/bin/who"])
    users: set[str] = set()
    for line in out.splitlines():
        if not line:
            continue
        users.add(line.split()[0])

    result: list[LoggedInUser] = []
    for username in sorted(users):
        try:
            uid = pwd.getpwnam(username).pw_uid
        except KeyError:
            continue
        result.append(
            LoggedInUser(username=username, uid=uid, is_admin=is_admin_user(username))
        )
    return result


def standard_users(users: Iterable[LoggedInUser]) -> list[LoggedInUser]:
    return [u for u in users if not u.is_admin]
