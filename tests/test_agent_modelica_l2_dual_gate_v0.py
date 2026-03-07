import unittest

from gateforge.agent_modelica_l2_dual_gate_v0 import _check_model_ok, _classify_infra_failure, _timeout_for_scale


class AgentModelicaL2DualGateV0Tests(unittest.TestCase):
    def test_check_model_ok_detects_success_marker(self) -> None:
        output = "Check of SmallRC completed successfully."
        self.assertTrue(_check_model_ok(output, "SmallRC"))

    def test_check_model_ok_rejects_missing_marker(self) -> None:
        output = "Failed to build model"
        self.assertFalse(_check_model_ok(output, "SmallRC"))

    def test_classify_infra_failure_patterns(self) -> None:
        self.assertEqual(_classify_infra_failure("TimeoutExpired"), "timeout")
        self.assertEqual(
            _classify_infra_failure("permission denied while trying to connect to the docker API"),
            "docker_permission_denied",
        )
        self.assertEqual(
            _classify_infra_failure("includes invalid characters for a local volume name"),
            "docker_volume_mount_invalid",
        )
        self.assertEqual(_classify_infra_failure("Failed to load package Modelica"), "msl_load_failed")
        self.assertEqual(_classify_infra_failure("No such file or directory"), "path_not_found")

    def test_timeout_for_scale_uses_profile_by_default(self) -> None:
        self.assertEqual(
            _timeout_for_scale(
                "small",
                timeout_sec=0,
                timeout_small_sec=180,
                timeout_medium_sec=240,
                timeout_large_sec=420,
            ),
            180,
        )
        self.assertEqual(
            _timeout_for_scale(
                "medium",
                timeout_sec=0,
                timeout_small_sec=180,
                timeout_medium_sec=240,
                timeout_large_sec=420,
            ),
            240,
        )
        self.assertEqual(
            _timeout_for_scale(
                "large",
                timeout_sec=0,
                timeout_small_sec=180,
                timeout_medium_sec=240,
                timeout_large_sec=420,
            ),
            420,
        )

    def test_timeout_for_scale_honors_override(self) -> None:
        self.assertEqual(
            _timeout_for_scale(
                "large",
                timeout_sec=90,
                timeout_small_sec=180,
                timeout_medium_sec=240,
                timeout_large_sec=420,
            ),
            90,
        )


if __name__ == "__main__":
    unittest.main()
