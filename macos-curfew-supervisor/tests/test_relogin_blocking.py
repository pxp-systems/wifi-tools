import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from daemon.state_store import StateStore


class ReloginBlockingStateTests(unittest.TestCase):
    def test_blocked_state_resets_on_new_nz_day(self):
        tz = ZoneInfo("Pacific/Auckland")
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "state.db")
            username = "alice"

            day_one_now = datetime(2026, 3, 9, 22, 31, tzinfo=tz)
            store.ensure_user_day_state(username=username, day_key="2026-03-09", now=day_one_now)
            store.set_blocked_for_day(username=username, day_key="2026-03-09", now=day_one_now)
            store.set_blocked_grace_until(
                username=username,
                until=datetime(2026, 3, 9, 22, 32, tzinfo=tz),
                now=day_one_now,
            )

            self.assertEqual(store.get_blocked_day(username), "2026-03-09")
            self.assertIsNotNone(store.get_blocked_grace_until(username))

            day_two_now = datetime(2026, 3, 10, 8, 0, tzinfo=tz)
            store.ensure_user_day_state(username=username, day_key="2026-03-10", now=day_two_now)

            self.assertIsNone(store.get_blocked_day(username))
            self.assertIsNone(store.get_blocked_grace_until(username))


if __name__ == "__main__":
    unittest.main()
