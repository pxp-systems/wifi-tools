import re
import unittest
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
        ssid_field.fill.assert_called_once_with("AG-1702262040")
        password_field.wait_for.assert_called_once_with(timeout=30000)
        password_field.fill.assert_called_once_with("98765")
        save_button.click.assert_called_once_with(timeout=120000)

    def test_generate_network_name_matches_pattern_ag_ddmmyyhhmm(self):
        with patch("wifi.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "AG-1702262040"
            name = wifi.generate_network_name()

        self.assertRegex(name, r"^AG-\d{10}$")
        self.assertTrue(re.match(r"^AG-\d{10}$", name))


if __name__ == "__main__":
    unittest.main()
