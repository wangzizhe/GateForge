import unittest

from gateforge.agent_modelica_l4_l5_reason_map_v0 import (
    map_l4_to_weekly_recommendation_reason_v0,
    normalize_l4_primary_reason_v0,
)


class AgentModelicaL4L5ReasonMapV0Tests(unittest.TestCase):
    def test_normalize_l4_reason_accepts_known(self) -> None:
        self.assertEqual(normalize_l4_primary_reason_v0("no_progress_window"), "no_progress_window")

    def test_normalize_l4_reason_rejects_unknown(self) -> None:
        self.assertEqual(normalize_l4_primary_reason_v0("custom_reason_x"), "reason_enum_unknown")

    def test_map_l4_reason_to_weekly_reason(self) -> None:
        self.assertEqual(
            map_l4_to_weekly_recommendation_reason_v0("apply_failed"),
            "apply_failed",
        )
        self.assertEqual(
            map_l4_to_weekly_recommendation_reason_v0("hard_checks_pass"),
            "threshold_not_met",
        )


if __name__ == "__main__":
    unittest.main()
