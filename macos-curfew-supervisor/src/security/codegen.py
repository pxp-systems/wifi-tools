from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
from datetime import datetime

from shared.time_utils import now_nz

SAFE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def build_message(username: str, when: datetime) -> str:
    return f"{when.strftime('%Y-%m-%d')}:{when.strftime('%H')}:{username}"


def derive_code(secret: bytes, username: str, when: datetime) -> str:
    message = build_message(username=username, when=when).encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    b32 = base64.b32encode(digest).decode("ascii").rstrip("=")
    filtered = "".join(ch for ch in b32 if ch in SAFE_ALPHABET)
    if len(filtered) < 5:
        raise RuntimeError("Unable to derive enough code characters")
    return filtered[:5]


def constant_time_code_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def main() -> None:
    from daemon.config import load_config

    parser = argparse.ArgumentParser(description="Generate deterministic curfew override code")
    parser.add_argument("--config", required=True, help="Path to supervisor.toml")
    parser.add_argument("--user", required=True, help="Target username")
    parser.add_argument("--hour", default=None, help="Optional NZ local hour (YYYY-MM-DDTHH)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.hour:
        when = datetime.strptime(args.hour, "%Y-%m-%dT%H").replace(tzinfo=cfg.timezone)
    else:
        when = now_nz().astimezone(cfg.timezone)

    code = derive_code(secret=cfg.secret_key, username=args.user, when=when)
    print(code)


if __name__ == "__main__":
    main()
