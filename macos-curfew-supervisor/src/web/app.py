from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request

from daemon.config import SupervisorConfig
from daemon.state_store import StateStore
from daemon.telegram import TelegramClient, format_event
from security.codegen import constant_time_code_equals, derive_code


def create_web_app(*, cfg: SupervisorConfig, store: StateStore, telegram: TelegramClient) -> Flask:
    template_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))

    @app.get("/warning")
    def warning_page():
        token = request.args.get("token", "")
        row = store.get_warning_token(token)
        if not row:
            return "Invalid warning token", 404

        return render_template(
            "warning.html",
            token=token,
            username=row["username"],
            deadline=row["deadline"],
        )

    @app.get("/status")
    def status():
        token = request.args.get("token", "")
        row = store.get_warning_token(token)
        if not row:
            return jsonify({"error": "invalid_token"}), 404

        username = row["username"]
        now = datetime.now(cfg.timezone)
        override_until = store.get_override_until(username)
        effective_deadline = override_until if override_until and override_until > now else datetime.fromisoformat(row["deadline"])
        return jsonify(
            {
                "username": username,
                "deadline": effective_deadline.isoformat(),
                "override_until": override_until.isoformat() if override_until else None,
                "now": now.isoformat(),
            }
        )

    @app.post("/override")
    def override():
        payload = request.get_json(silent=True) or {}
        token = str(payload.get("token", "")).strip()
        code = str(payload.get("code", "")).strip().upper()

        row = store.get_warning_token(token)
        if not row:
            return jsonify({"ok": False, "error": "invalid_token"}), 404

        username = row["username"]
        now = datetime.now(cfg.timezone)

        failed_since = now - timedelta(minutes=10)
        failed_count = store.count_recent_failed_attempts(username=username, since=failed_since)
        if failed_count >= cfg.max_override_attempts_per_10_min:
            store.log_override_attempt(
                ts=now,
                username=username,
                success=False,
                source_ip=request.remote_addr or "127.0.0.1",
                detail="rate_limited",
            )
            return jsonify({"ok": False, "error": "too_many_attempts"}), 429

        expected = derive_code(secret=cfg.secret_key, username=username, when=now)
        if not constant_time_code_equals(expected, code):
            store.log_override_attempt(
                ts=now,
                username=username,
                success=False,
                source_ip=request.remote_addr or "127.0.0.1",
                detail="invalid_code",
            )
            if failed_count + 1 >= 3:
                telegram.send(format_event("repeated invalid override attempts", username=username))
            return jsonify({"ok": False, "error": "invalid_code"}), 400

        deadline = datetime.fromisoformat(row["deadline"])
        new_deadline = max(deadline, now) + timedelta(minutes=cfg.extension_minutes)
        store.set_override_until(username=username, until=new_deadline, now=now)
        store.consume_warning_token(token=token, now=now)
        store.log_override_attempt(
            ts=now,
            username=username,
            success=True,
            source_ip=request.remote_addr or "127.0.0.1",
            detail=f"override_until={new_deadline.isoformat()}",
        )
        telegram.send(
            format_event(
                "override accepted",
                username=username,
                extra=f"until={new_deadline.isoformat()}",
            )
        )
        return jsonify({"ok": True, "deadline": new_deadline.isoformat()})

    @app.get("/")
    def root():
        return redirect("/warning", code=302)

    return app
