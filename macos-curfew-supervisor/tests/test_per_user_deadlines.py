import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from daemon.scheduler import base_deadline_for_day, extend_deadline


class PerUserDeadlineTests(unittest.TestCase):
    def test_base_deadline_uses_2230(self):
        now = datetime(2026, 3, 9, 21, 0, tzinfo=ZoneInfo("Pacific/Auckland"))
        deadline = base_deadline_for_day(now, "22:30")
        self.assertEqual(deadline.hour, 22)
        self.assertEqual(deadline.minute, 30)

    def test_extension_adds_30_minutes(self):
        base = datetime(2026, 3, 9, 22, 30, tzinfo=ZoneInfo("Pacific/Auckland"))
        self.assertEqual(extend_deadline(base, 30).strftime("%H:%M"), "23:00")


if __name__ == "__main__":
    unittest.main()
