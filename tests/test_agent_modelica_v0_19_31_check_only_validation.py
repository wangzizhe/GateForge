from __future__ import annotations

import unittest

from gateforge.agent_modelica_live_executor_v1 import _validation_passed


class TestV01931CheckOnlyValidation(unittest.TestCase):
    def test_full_mode_requires_check_and_simulate(self):
        self.assertFalse(_validation_passed(validation_mode="full", check_ok=True, simulate_ok=False))
        self.assertTrue(_validation_passed(validation_mode="full", check_ok=True, simulate_ok=True))

    def test_check_only_mode_requires_check_only(self):
        self.assertTrue(_validation_passed(validation_mode="check_only", check_ok=True, simulate_ok=False))
        self.assertFalse(_validation_passed(validation_mode="check_only", check_ok=False, simulate_ok=True))


if __name__ == "__main__":
    unittest.main()
