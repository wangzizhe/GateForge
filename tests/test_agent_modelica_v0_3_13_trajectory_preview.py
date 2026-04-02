from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_13_trajectory_preview import (
    build_preview_row,
    preview_surface_fix,
)
from gateforge.agent_modelica_v0_3_13_residual_signal_whitelist import DEFAULT_SIGNAL_CLUSTERS


TASK = {
    "task_id": "demo",
    "declared_failure_type": "simulate_error",
    "failure_type": "simulate_error",
    "source_model_path": "demo.mo",
    "source_model_text": "model Demo\n  parameter Real m = 0.0;\nequation\nend Demo;\n",
    "mutated_model_text": (
        "model Demo\n"
        "  parameter Real m = 0.0;\n"
        "  parameter Real __gf_tau_12345678 = 1e-9; // GateForge mutation: zero time constant\n"
        "equation\n"
        "end Demo;\n"
    ),
}


class AgentModelicaV0313TrajectoryPreviewTests(unittest.TestCase):
    def test_preview_surface_fix_detects_simulate_injection_rule(self) -> None:
        preview = preview_surface_fix(TASK)

        self.assertTrue(preview["surface_fixable_by_rule"])
        self.assertEqual(preview["surface_rule_id"], "rule_simulate_error_injection_repair")
        self.assertFalse(preview["post_rule_source_repair_applied"])

    def test_build_preview_row_admits_whitelisted_residual(self) -> None:
        whitelist = {"clusters": DEFAULT_SIGNAL_CLUSTERS}

        def fake_runner(task: dict, model_text: str) -> dict:
            self.assertNotIn("__gf_tau_12345678", model_text)
            return {
                "return_code": 0,
                "check_model_pass": True,
                "simulate_pass": False,
                "diagnostic": {
                    "stage_subtype": "stage_4_initialization_singularity",
                    "error_type": "simulate_error",
                    "reason": "initialization failed",
                },
            }

        row = build_preview_row(task=TASK, whitelist_payload=whitelist, preview_runner=fake_runner)

        self.assertTrue(row["preview_admission"])
        self.assertEqual(row["residual_signal_cluster_id"], "initialization_parameter_recovery")

    def test_build_preview_row_rejects_success_without_residual(self) -> None:
        whitelist = {"clusters": DEFAULT_SIGNAL_CLUSTERS}

        def fake_runner(task: dict, model_text: str) -> dict:
            return {
                "return_code": 0,
                "check_model_pass": True,
                "simulate_pass": True,
                "diagnostic": {
                    "stage_subtype": "stage_0_none",
                    "error_type": "none",
                    "reason": "",
                },
            }

        row = build_preview_row(task=TASK, whitelist_payload=whitelist, preview_runner=fake_runner)

        self.assertFalse(row["preview_admission"])
        self.assertEqual(row["preview_reason"], "post_rule_success_without_residual")


if __name__ == "__main__":
    unittest.main()
