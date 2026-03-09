from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import tomllib


@dataclass(frozen=True)
class SupervisorConfig:
    timezone: ZoneInfo
    base_deadline: str
    warning_offsets_minutes: list[int]
    extension_minutes: int
    relogin_grace_seconds: int
    loop_interval_seconds: int
    web_host: str
    web_port: int
    max_override_attempts_per_10_min: int
    db_path: Path
    log_path: Path
    warning_drop_dir: Path
    secret_file: Path
    telegram_bot_token: str
    telegram_chat_ids: list[str]
    secret_key: bytes


def _read_secret(secret_file: Path) -> bytes:
    value = secret_file.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"Secret file is empty: {secret_file}")
    return value.encode("utf-8")


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise KeyError(f"Missing config key: {key}")
    return data[key]


def load_config(path: str) -> SupervisorConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    timezone = ZoneInfo(str(_require(raw, "timezone")))
    secret_file = Path(str(_require(raw, "secret_file")))
    return SupervisorConfig(
        timezone=timezone,
        base_deadline=str(_require(raw, "base_deadline")),
        warning_offsets_minutes=[int(v) for v in _require(raw, "warning_offsets_minutes")],
        extension_minutes=int(_require(raw, "extension_minutes")),
        relogin_grace_seconds=int(raw.get("relogin_grace_seconds", 60)),
        loop_interval_seconds=int(raw.get("loop_interval_seconds", 20)),
        web_host=str(raw.get("web_host", "127.0.0.1")),
        web_port=int(raw.get("web_port", 8765)),
        max_override_attempts_per_10_min=int(raw.get("max_override_attempts_per_10_min", 5)),
        db_path=Path(str(_require(raw, "db_path"))),
        log_path=Path(str(_require(raw, "log_path"))),
        warning_drop_dir=Path(str(_require(raw, "warning_drop_dir"))),
        secret_file=secret_file,
        telegram_bot_token=str(raw.get("telegram_bot_token", "")).strip(),
        telegram_chat_ids=[str(v).strip() for v in raw.get("telegram_chat_ids", []) if str(v).strip()],
        secret_key=_read_secret(secret_file),
    )
