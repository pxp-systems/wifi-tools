from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LoggedInUser:
    username: str
    uid: int
    is_admin: bool


@dataclass(frozen=True)
class UserCurfewState:
    username: str
    base_deadline: datetime
    effective_deadline: datetime
    override_until: Optional[datetime]


@dataclass(frozen=True)
class WarningEvent:
    username: str
    warning_offset_minutes: int
    deadline: datetime
    token: str
