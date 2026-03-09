import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from security.codegen import derive_code


class CodegenTests(unittest.TestCase):
    def test_codegen_is_deterministic_for_same_inputs(self):
        secret = b"test-secret"
        when = datetime(2026, 3, 9, 22, 0, tzinfo=ZoneInfo("Pacific/Auckland"))

        code_a = derive_code(secret=secret, username="alice", when=when)
        code_b = derive_code(secret=secret, username="alice", when=when)

        self.assertEqual(code_a, code_b)
        self.assertEqual(len(code_a), 5)


if __name__ == "__main__":
    unittest.main()
