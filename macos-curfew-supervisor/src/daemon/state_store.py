from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class OverrideRow:
    username: str
    override_until: datetime


class StateStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_state (
                    username TEXT PRIMARY KEY,
                    state_day_key TEXT NULL,
                    override_until TEXT NULL,
                    blocked_day_key TEXT NULL,
                    blocked_grace_until TEXT NULL,
                    warning_marks TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS override_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    username TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    source_ip TEXT NOT NULL,
                    detail TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS warning_tokens (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT NULL
                );
                """
            )
            self._ensure_column(conn, "user_state", "state_day_key", "TEXT NULL")
            self._ensure_column(conn, "user_state", "blocked_day_key", "TEXT NULL")
            self._ensure_column(conn, "user_state", "blocked_grace_until", "TEXT NULL")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in columns}
        if column in existing:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _ensure_user_row(self, username: str, now_iso: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_state(username, state_day_key, override_until, blocked_day_key, blocked_grace_until, warning_marks, updated_at)
                VALUES (?, NULL, NULL, NULL, NULL, '{}', ?)
                ON CONFLICT(username) DO NOTHING
                """,
                (username, now_iso),
            )

    def ensure_user_day_state(self, username: str, day_key: str, now: datetime) -> None:
        now_iso = now.isoformat()
        self._ensure_user_row(username, now_iso)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_day_key FROM user_state WHERE username=?",
                (username,),
            ).fetchone()
            current_day = row["state_day_key"] if row else None
            if current_day == day_key:
                return
            conn.execute(
                """
                UPDATE user_state
                SET state_day_key=?,
                    override_until=NULL,
                    blocked_day_key=NULL,
                    blocked_grace_until=NULL,
                    warning_marks='{}',
                    updated_at=?
                WHERE username=?
                """,
                (day_key, now_iso, username),
            )

    def set_override_until(self, username: str, until: datetime, now: datetime) -> None:
        now_iso = now.isoformat()
        self._ensure_user_row(username, now_iso)
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET override_until=?, updated_at=? WHERE username=?",
                (until.isoformat(), now_iso, username),
            )

    def get_override_until(self, username: str) -> Optional[datetime]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT override_until FROM user_state WHERE username=?",
                (username,),
            ).fetchone()
        if not row or not row["override_until"]:
            return None
        return datetime.fromisoformat(row["override_until"])

    def clear_override_if_expired(self, username: str, now: datetime) -> None:
        current = self.get_override_until(username)
        if current is None or current > now:
            return
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET override_until=NULL, updated_at=? WHERE username=?",
                (now.isoformat(), username),
            )

    def mark_warning_sent(self, username: str, warning_key: str, now: datetime) -> None:
        now_iso = now.isoformat()
        self._ensure_user_row(username, now_iso)
        marks = self.get_warning_marks(username)
        marks[warning_key] = now_iso
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET warning_marks=?, updated_at=? WHERE username=?",
                (json.dumps(marks), now_iso, username),
            )

    def get_warning_marks(self, username: str) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT warning_marks FROM user_state WHERE username=?",
                (username,),
            ).fetchone()
        if not row:
            return {}
        return json.loads(row["warning_marks"])

    def reset_warnings_for_new_day(self, username: str, day_key: str, now: datetime) -> None:
        marks = self.get_warning_marks(username)
        if all(k.startswith(day_key) for k in marks.keys()):
            return
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET warning_marks=?, updated_at=? WHERE username=?",
                (json.dumps({}), now.isoformat(), username),
            )

    def log_override_attempt(
        self,
        *,
        ts: datetime,
        username: str,
        success: bool,
        source_ip: str,
        detail: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO override_attempts(ts, username, success, source_ip, detail)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ts.isoformat(), username, 1 if success else 0, source_ip, detail),
            )

    def count_recent_failed_attempts(self, username: str, since: datetime) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM override_attempts
                WHERE username=? AND success=0 AND ts >= ?
                """,
                (username, since.isoformat()),
            ).fetchone()
        return int(row["cnt"] if row else 0)

    def set_blocked_for_day(self, username: str, day_key: str, now: datetime) -> None:
        now_iso = now.isoformat()
        self._ensure_user_row(username, now_iso)
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET blocked_day_key=?, updated_at=? WHERE username=?",
                (day_key, now_iso, username),
            )

    def get_blocked_day(self, username: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT blocked_day_key FROM user_state WHERE username=?",
                (username,),
            ).fetchone()
        if not row:
            return None
        return row["blocked_day_key"]

    def set_blocked_grace_until(self, username: str, until: datetime, now: datetime) -> None:
        now_iso = now.isoformat()
        self._ensure_user_row(username, now_iso)
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET blocked_grace_until=?, updated_at=? WHERE username=?",
                (until.isoformat(), now_iso, username),
            )

    def get_blocked_grace_until(self, username: str) -> Optional[datetime]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT blocked_grace_until FROM user_state WHERE username=?",
                (username,),
            ).fetchone()
        if not row or not row["blocked_grace_until"]:
            return None
        return datetime.fromisoformat(row["blocked_grace_until"])

    def clear_blocked_grace_until(self, username: str, now: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET blocked_grace_until=NULL, updated_at=? WHERE username=?",
                (now.isoformat(), username),
            )

    def create_warning_token(self, token: str, username: str, deadline: datetime, now: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO warning_tokens(token, username, deadline, created_at, consumed_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (token, username, deadline.isoformat(), now.isoformat()),
            )

    def get_warning_token(self, token: str) -> Optional[dict[str, str]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token, username, deadline, created_at, consumed_at FROM warning_tokens WHERE token=?",
                (token,),
            ).fetchone()
        if row is None:
            return None
        return {
            "token": row["token"],
            "username": row["username"],
            "deadline": row["deadline"],
            "created_at": row["created_at"],
            "consumed_at": row["consumed_at"],
        }

    def consume_warning_token(self, token: str, now: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE warning_tokens SET consumed_at=? WHERE token=?",
                (now.isoformat(), token),
            )
