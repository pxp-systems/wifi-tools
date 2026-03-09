from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def nz_tz() -> ZoneInfo:
    return ZoneInfo("Pacific/Auckland")


def now_nz() -> datetime:
    return datetime.now(tz=nz_tz())


def parse_hhmm(value: str) -> tuple[int, int]:
    hour_s, minute_s = value.split(":", 1)
    hour = int(hour_s)
    minute = int(minute_s)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid HH:MM value: {value}")
    return hour, minute
