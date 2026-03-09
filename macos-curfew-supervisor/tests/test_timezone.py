import unittest

from shared.time_utils import now_nz


class TimezoneTests(unittest.TestCase):
    def test_now_nz_uses_auckland_timezone(self):
        value = now_nz()
        self.assertIsNotNone(value.tzinfo)
        self.assertEqual(str(value.tzinfo), "Pacific/Auckland")


if __name__ == "__main__":
    unittest.main()
