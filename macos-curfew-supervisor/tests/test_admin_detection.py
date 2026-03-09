import unittest
from unittest.mock import patch

from daemon import session_manager


class AdminDetectionTests(unittest.TestCase):
    def test_is_admin_user_true_when_dsmemberutil_reports_membership(self):
        with patch.object(session_manager, "_run", return_value="user is a member of the group"):
            self.assertTrue(session_manager.is_admin_user("alice"))

    def test_is_admin_user_false_when_not_member(self):
        with patch.object(session_manager, "_run", return_value="user is not a member"):
            self.assertFalse(session_manager.is_admin_user("alice"))


if __name__ == "__main__":
    unittest.main()
