import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import wifi


class UpdateGuestNetworkTests(unittest.TestCase):
    def setUp(self):
        self.original_guest_ssid_selector = wifi.GUEST_SSID_SELECTOR
        self.original_guest_password_selector = wifi.GUEST_PASSWORD_SELECTOR
        self.original_save_button_selector = wifi.SAVE_BUTTON_SELECTOR

    def tearDown(self):
        wifi.GUEST_SSID_SELECTOR = self.original_guest_ssid_selector
        wifi.GUEST_PASSWORD_SELECTOR = self.original_guest_password_selector
        wifi.SAVE_BUTTON_SELECTOR = self.original_save_button_selector

    def test_updates_ssid_and_password(self):
        wifi.GUEST_SSID_SELECTOR = "#ssid"
        wifi.GUEST_PASSWORD_SELECTOR = "#passphrase"
        wifi.SAVE_BUTTON_SELECTOR = "button:has-text(\"Apply\")"

        frame = MagicMock()
        ssid_field = MagicMock()
        password_field = MagicMock()
        save_button = MagicMock()

        def locator_side_effect(selector):
            mapping = {
                wifi.GUEST_SSID_SELECTOR: ssid_field,
                wifi.GUEST_PASSWORD_SELECTOR: password_field,
                wifi.SAVE_BUTTON_SELECTOR: save_button,
            }
            return mapping[selector]

        frame.locator.side_effect = locator_side_effect

        wifi._update_guest_network(frame, "98765", "AG-1702262040")

        ssid_field.wait_for.assert_called_once_with(timeout=30000)
        ssid_field.click.assert_called_once_with(timeout=10000)
        ssid_field.press.assert_called_once_with("ControlOrMeta+a")
        ssid_field.type.assert_called_once_with("AG-1702262040")
        password_field.wait_for.assert_called_once_with(timeout=30000)
        password_field.click.assert_called_once_with(timeout=10000)
        password_field.press.assert_called_once_with("ControlOrMeta+a")
        password_field.type.assert_called_once_with("98765")
        save_button.click.assert_called_once_with(timeout=120000)

    def test_generate_network_name_matches_pattern_ag_ddmmyyhhmm(self):
        with patch("wifi.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "AG-1702262040"
            name = wifi.generate_network_name()

        self.assertRegex(name, r"^AG-\d{10}$")
        self.assertTrue(re.match(r"^AG-\d{10}$", name))


class WatcherLockTests(unittest.TestCase):
    def setUp(self):
        self.original_watch_lock_file = wifi.WATCH_LOCK_FILE
        self.original_watch_lock_handle = wifi._WATCH_LOCK_HANDLE

    def tearDown(self):
        if wifi._WATCH_LOCK_HANDLE is not None:
            wifi._WATCH_LOCK_HANDLE.close()
        wifi._WATCH_LOCK_HANDLE = self.original_watch_lock_handle
        wifi.WATCH_LOCK_FILE = self.original_watch_lock_file

    def test_acquire_watch_lock_blocks_second_watcher(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wifi.WATCH_LOCK_FILE = Path(tmp_dir) / "wifi-watch.lock"
            wifi._WATCH_LOCK_HANDLE = None

            wifi._acquire_watch_lock()

            with self.assertRaises(RuntimeError):
                wifi._acquire_watch_lock()


class GuestNetworkToggleTests(unittest.TestCase):
    def setUp(self):
        self.original_guest_enable_selector = wifi.GUEST_ENABLE_SELECTOR
        self.original_save_button_selector = wifi.SAVE_BUTTON_SELECTOR
        wifi.GUEST_ENABLE_SELECTOR = "#enable_guest"
        wifi.SAVE_BUTTON_SELECTOR = "button:has-text(\"Apply\")"

    def tearDown(self):
        wifi.GUEST_ENABLE_SELECTOR = self.original_guest_enable_selector
        wifi.SAVE_BUTTON_SELECTOR = self.original_save_button_selector

    def _frame(self, currently_on):
        toggle = MagicMock()
        toggle.is_checked.return_value = currently_on
        save_button = MagicMock()
        frame = MagicMock()
        frame.locator.side_effect = lambda selector: {
            wifi.GUEST_ENABLE_SELECTOR: toggle,
            wifi.SAVE_BUTTON_SELECTOR: save_button,
        }[selector]
        return frame, toggle, save_button

    def test_turns_guest_network_off_and_applies(self):
        frame, toggle, save_button = self._frame(currently_on=True)

        wifi._set_guest_network_enabled(frame, False)

        toggle.wait_for.assert_called_once_with(timeout=30000)
        toggle.uncheck.assert_called_once_with(timeout=10000)
        toggle.check.assert_not_called()
        save_button.click.assert_called_once_with(timeout=120000)

    def test_turns_guest_network_on_and_applies(self):
        frame, toggle, save_button = self._frame(currently_on=False)

        wifi._set_guest_network_enabled(frame, True)

        toggle.check.assert_called_once_with(timeout=10000)
        save_button.click.assert_called_once_with(timeout=120000)

    def test_skips_apply_when_already_in_desired_state(self):
        frame, toggle, save_button = self._frame(currently_on=False)

        wifi._set_guest_network_enabled(frame, False)

        toggle.uncheck.assert_not_called()
        save_button.click.assert_not_called()

    def test_falls_back_to_click_for_non_checkbox_switch(self):
        frame, toggle, save_button = self._frame(currently_on=True)
        toggle.uncheck.side_effect = Exception("not a checkbox")

        wifi._set_guest_network_enabled(frame, False)

        toggle.click.assert_called_once_with(timeout=10000)
        save_button.click.assert_called_once_with(timeout=120000)


class DowntimeScheduleTests(unittest.TestCase):
    @staticmethod
    def _at(day, hhmm):
        # 2026-03-09 is a Monday, so day=0 -> Monday ... day=6 -> Sunday.
        hour, minute = (int(part) for part in hhmm.split(":"))
        return datetime(2026, 3, 9 + day, hour, minute)

    def test_overnight_window_covers_both_sides_of_midnight(self):
        kwargs = {"start": "22:30", "end": "06:30", "days": "all"}
        self.assertFalse(wifi.is_downtime(self._at(0, "22:29"), **kwargs))
        self.assertTrue(wifi.is_downtime(self._at(0, "22:30"), **kwargs))
        self.assertTrue(wifi.is_downtime(self._at(0, "23:59"), **kwargs))
        self.assertTrue(wifi.is_downtime(self._at(1, "00:01"), **kwargs))
        self.assertTrue(wifi.is_downtime(self._at(1, "06:29"), **kwargs))
        self.assertFalse(wifi.is_downtime(self._at(1, "06:30"), **kwargs))
        self.assertFalse(wifi.is_downtime(self._at(1, "12:00"), **kwargs))

    def test_same_day_window(self):
        kwargs = {"start": "09:00", "end": "17:00", "days": "all"}
        self.assertFalse(wifi.is_downtime(self._at(0, "08:59"), **kwargs))
        self.assertTrue(wifi.is_downtime(self._at(0, "09:00"), **kwargs))
        self.assertFalse(wifi.is_downtime(self._at(0, "17:00"), **kwargs))
        self.assertFalse(wifi.is_downtime(self._at(0, "23:00"), **kwargs))

    def test_day_filter_applies_to_window_start_day(self):
        kwargs = {"start": "22:30", "end": "06:30", "days": "sun"}
        # Sunday night into Monday morning is covered ...
        self.assertTrue(wifi.is_downtime(self._at(6, "23:00"), **kwargs))
        self.assertTrue(wifi.is_downtime(self._at(7, "01:00"), **kwargs))
        # ... but Monday night is not.
        self.assertFalse(wifi.is_downtime(self._at(0, "23:00"), **kwargs))

    def test_zero_length_window_is_never_downtime(self):
        kwargs = {"start": "22:00", "end": "22:00", "days": "all"}
        self.assertFalse(wifi.is_downtime(self._at(0, "22:00"), **kwargs))

    def test_parse_days_aliases(self):
        self.assertEqual(wifi.parse_days("all"), set(range(7)))
        self.assertEqual(wifi.parse_days("weekdays"), {0, 1, 2, 3, 4})
        self.assertEqual(wifi.parse_days("weekends"), {5, 6})
        self.assertEqual(wifi.parse_days("mon, wednesday,FRI"), {0, 2, 4})
        with self.assertRaises(ValueError):
            wifi.parse_days("funday")

    def test_parse_hhmm_rejects_bad_values(self):
        for bad in ["", "7:5", "24:00", "12:60", "noon"]:
            with self.assertRaises(ValueError):
                wifi.parse_hhmm(bad)


class ApplyScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.original_state_file = wifi.GUEST_STATE_FILE
        self.original_enabled = wifi.DOWNTIME_ENABLED
        self.original_notify = wifi.DOWNTIME_NOTIFY
        wifi.GUEST_STATE_FILE = Path(self.tmp_dir.name) / "guest_state"
        wifi.DOWNTIME_ENABLED = True
        wifi.DOWNTIME_NOTIFY = False

    def tearDown(self):
        wifi.GUEST_STATE_FILE = self.original_state_file
        wifi.DOWNTIME_ENABLED = self.original_enabled
        wifi.DOWNTIME_NOTIFY = self.original_notify

    def test_applies_and_records_state_on_first_run(self):
        with patch("wifi.desired_guest_state", return_value=False), \
                patch("wifi.set_guest_network_enabled", return_value=True) as toggle:
            self.assertFalse(wifi.apply_schedule())

        toggle.assert_called_once_with(False)
        self.assertFalse(wifi.load_guest_state())

    def test_is_a_no_op_when_state_already_matches(self):
        wifi.save_guest_state(False)

        with patch("wifi.desired_guest_state", return_value=False), \
                patch("wifi.set_guest_network_enabled") as toggle:
            wifi.apply_schedule()

        toggle.assert_not_called()

    def test_retries_next_tick_when_router_update_fails(self):
        with patch("wifi.desired_guest_state", return_value=False), \
                patch("wifi.set_guest_network_enabled", return_value=False):
            self.assertIsNone(wifi.apply_schedule())

        # No state recorded, so the next tick tries again.
        self.assertIsNone(wifi.load_guest_state())

    def test_notifies_telegram_on_state_change(self):
        wifi.DOWNTIME_NOTIFY = True

        with patch("wifi.desired_guest_state", return_value=False), \
                patch("wifi.set_guest_network_enabled", return_value=True), \
                patch("wifi.send_telegram_text") as notify:
            wifi.apply_schedule()

        notify.assert_called_once()

    def test_disabled_schedule_does_nothing(self):
        wifi.DOWNTIME_ENABLED = False

        with patch("wifi.set_guest_network_enabled") as toggle:
            self.assertIsNone(wifi.apply_schedule())

        toggle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
