from __future__ import annotations

import argparse
import logging
import json
import secrets
import threading
import time
from datetime import datetime, timedelta

from daemon.config import SupervisorConfig, load_config
from daemon.enforcement import force_logout_user
from daemon.logging_utils import setup_logging
from daemon.scheduler import base_deadline_for_day, warning_moment
from daemon.session_manager import list_console_users, standard_users
from daemon.state_store import StateStore
from daemon.telegram import TelegramClient, format_event
from web.app import create_web_app

LOGGER = logging.getLogger(__name__)


def _deadline_for_user(cfg: SupervisorConfig, store: StateStore, username: str, now: datetime) -> datetime:
    base = base_deadline_for_day(now, cfg.base_deadline)
    override_until = store.get_override_until(username)
    if override_until and override_until > base:
        return override_until
    return base


def _warning_key(now: datetime, offset: int | str) -> str:
    return f"{now.strftime('%Y-%m-%d')}-{offset}"


def _issue_warning(
    *,
    cfg: SupervisorConfig,
    store: StateStore,
    telegram: TelegramClient,
    username: str,
    offset: int | str,
    deadline: datetime,
    now: datetime,
) -> None:
    token = secrets.token_urlsafe(24)
    store.create_warning_token(token=token, username=username, deadline=deadline, now=now)
    payload = {
        "token": token,
        "username": username,
        "deadline": deadline.isoformat(),
        "created_at": now.isoformat(),
    }
    cfg.warning_drop_dir.mkdir(parents=True, exist_ok=True)
    warning_file = cfg.warning_drop_dir / f"{username}-{token}.json"
    warning_file.write_text(json.dumps(payload), encoding="utf-8")
    store.mark_warning_sent(username=username, warning_key=_warning_key(now, offset), now=now)
    if isinstance(offset, int):
        event_name = f"{offset}-minute warning"
    else:
        event_name = str(offset)
    telegram.send(format_event(event_name, username=username, extra=f"deadline={deadline.isoformat()}"))


def _handle_blocked_user_relogin(
    *,
    cfg: SupervisorConfig,
    store: StateStore,
    telegram: TelegramClient,
    username: str,
    deadline: datetime,
    now: datetime,
) -> bool:
    if now < deadline:
        return False

    grace_until = store.get_blocked_grace_until(username)
    if grace_until is None:
        grace_until = now + timedelta(seconds=cfg.relogin_grace_seconds)
        _issue_warning(
            cfg=cfg,
            store=store,
            telegram=telegram,
            username=username,
            offset="relogin-grace",
            deadline=grace_until,
            now=now,
        )
        store.set_blocked_grace_until(username=username, until=grace_until, now=now)
        telegram.send(
            format_event(
                "relogin grace started",
                username=username,
                extra=f"grace_until={grace_until.isoformat()}",
            )
        )
        return True

    if now >= grace_until:
        users = {u.username: u for u in standard_users(list_console_users())}
        user = users.get(username)
        if user is not None:
            force_logout_user(user)
            telegram.send(format_event("forced logout executed", username=username, extra="reason=relogin_no_override"))
        store.clear_blocked_grace_until(username=username, now=now)
        return True

    return True


def run_loop(cfg: SupervisorConfig) -> None:
    store = StateStore(cfg.db_path)
    telegram = TelegramClient(cfg.telegram_bot_token, cfg.telegram_chat_ids)

    app = create_web_app(cfg=cfg, store=store, telegram=telegram)
    threading.Thread(
        target=lambda: app.run(host=cfg.web_host, port=cfg.web_port, debug=False, use_reloader=False),
        daemon=True,
    ).start()

    telegram.send(format_event("daemon started"))

    while True:
        now = datetime.now(cfg.timezone)
        try:
            users = standard_users(list_console_users())
            day_key = now.strftime("%Y-%m-%d")
            for user in users:
                store.ensure_user_day_state(user.username, day_key=day_key, now=now)
                store.clear_override_if_expired(user.username, now)
                store.reset_warnings_for_new_day(user.username, day_key=day_key, now=now)

                deadline = _deadline_for_user(cfg, store, user.username, now)

                blocked_day = store.get_blocked_day(user.username)
                if blocked_day == day_key:
                    if _handle_blocked_user_relogin(
                        cfg=cfg,
                        store=store,
                        telegram=telegram,
                        username=user.username,
                        deadline=deadline,
                        now=now,
                    ):
                        continue

                marks = store.get_warning_marks(user.username)

                for offset in sorted(cfg.warning_offsets_minutes, reverse=True):
                    key = _warning_key(now, offset)
                    if key in marks:
                        continue
                    when = warning_moment(deadline, offset)
                    if now >= when and now < deadline:
                        _issue_warning(
                            cfg=cfg,
                            store=store,
                            telegram=telegram,
                            username=user.username,
                            offset=offset,
                            deadline=deadline,
                            now=now,
                        )

                if now >= deadline:
                    store.set_blocked_for_day(user.username, day_key=day_key, now=now)
                    store.clear_blocked_grace_until(username=user.username, now=now)
                    force_logout_user(user)
                    telegram.send(format_event("forced logout executed", username=user.username))

        except Exception as exc:
            LOGGER.exception("main loop error: %s", exc)
            telegram.send(format_event("daemon error", extra=str(exc)))

        time.sleep(cfg.loop_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="macOS Curfew Supervisor daemon")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg.log_path)
    run_loop(cfg)


if __name__ == "__main__":
    main()
