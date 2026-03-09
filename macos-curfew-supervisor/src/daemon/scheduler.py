from __future__ import annotations

from datetime import datetime, timedelta

from shared.time_utils import parse_hhmm


def base_deadline_for_day(now_local: datetime, base_deadline_hhmm: str) -> datetime:
    hour, minute = parse_hhmm(base_deadline_hhmm)
    return now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)


def warning_moment(deadline_local: datetime, offset_minutes: int) -> datetime:
    return deadline_local - timedelta(minutes=offset_minutes)


def extend_deadline(deadline_local: datetime, extension_minutes: int) -> datetime:
    return deadline_local + timedelta(minutes=extension_minutes)
