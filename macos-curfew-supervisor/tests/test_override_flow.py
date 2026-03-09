import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from daemon.state_store import StateStore
from security.codegen import derive_code


class DummyTelegram:
    def __init__(self):
        self.messages = []

    def send(self, text: str) -> None:
        self.messages.append(text)


def _cfg(tmp_path: Path):
    secret_file = tmp_path / "secret.key"
    secret_file.write_text("test-secret", encoding="utf-8")
    return SimpleNamespace(
        timezone=ZoneInfo("Pacific/Auckland"),
        extension_minutes=30,
        max_override_attempts_per_10_min=5,
        secret_key=b"test-secret",
        web_host="127.0.0.1",
        web_port=8765,
    )


class OverrideFlowTests(unittest.TestCase):
    def test_override_success_updates_deadline(self):
        import tempfile
        try:
            from web import app as web_app_module
            from web.app import create_web_app
        except ModuleNotFoundError:
            self.skipTest("Flask not installed in current interpreter")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg = _cfg(tmp_path)
            store = StateStore(tmp_path / "state.db")
            telegram = DummyTelegram()
            app = create_web_app(cfg=cfg, store=store, telegram=telegram)

            now = datetime(2026, 3, 9, 22, 10, tzinfo=cfg.timezone)
            deadline = datetime(2026, 3, 9, 22, 30, tzinfo=cfg.timezone)
            token = "tok-1"
            store.create_warning_token(token=token, username="alice", deadline=deadline, now=now)

            code = derive_code(secret=cfg.secret_key, username="alice", when=now)

            class FrozenDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return now if tz else now.replace(tzinfo=None)

            with patch.object(web_app_module, "datetime", FrozenDateTime):
                with app.test_client() as client:
                    response = client.post("/override", json={"token": token, "code": code})
                    self.assertEqual(response.status_code, 200)
                    body = response.get_json()
                    self.assertTrue(body["ok"])

            self.assertIsNotNone(store.get_override_until("alice"))


if __name__ == "__main__":
    unittest.main()
