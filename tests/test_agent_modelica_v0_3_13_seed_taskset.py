from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_seed_taskset import (
    FAMILY_INITIALIZATION,
    FAMILY_RUNTIME,
    build_v0_3_13_seed_taskset,
)


class AgentModelicaV0313SeedTasksetTests(unittest.TestCase):
    def test_builds_seed_taskset_from_audit_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "audit.json"
            preview = root / "preview.json"
            audit.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": "runtime_case",
                                "preview_admission": True,
                                "success_pattern": "rule_then_llm_multiround_success",
                                "residual_signal_cluster_id": "runtime_parameter_recovery",
                                "hidden_base_operator": "init_value_collapse",
                                "masking_pattern": "residual_visible_before_surface_cleanup",
                                "surface_rule_id": "rule_simulate_error_injection_repair",
                                "surface_rule_reason": "removed_gf_simulate_injection",
                                "first_attempt_stage_subtype": "stage_5_runtime_numerical_instability",
                                "second_attempt_stage_subtype": "stage_5_runtime_numerical_instability",
                                "llm_plan_candidate_parameters": ["m"],
                                "resolution_path": "rule_then_llm",
                                "rounds_used": 3,
                            },
                            {
                                "task_id": "init_case",
                                "preview_admission": True,
                                "success_pattern": "rule_then_llm_multiround_success",
                                "residual_signal_cluster_id": "initialization_parameter_recovery",
                                "hidden_base_operator": "init_equation_sign_flip",
                                "masking_pattern": "surface_masks_residual",
                                "surface_rule_id": "rule_simulate_error_injection_repair",
                                "surface_rule_reason": "removed_gf_simulate_injection",
                                "first_attempt_stage_subtype": "stage_1_parse_syntax",
                                "second_attempt_stage_subtype": "stage_4_initialization_singularity",
                                "llm_plan_candidate_parameters": ["x"],
                                "resolution_path": "rule_then_llm",
                                "rounds_used": 3,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            preview.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": "runtime_case",
                                "surface_fixable_by_rule": True,
                                "surface_rule_id": "rule_simulate_error_injection_repair",
                                "post_rule_residual_stage": "stage_5_runtime_numerical_instability",
                                "post_rule_residual_error_type": "numerical_instability",
                                "post_rule_residual_reason": "division by zero",
                                "preview_admission": True,
                            },
                            {
                                "task_id": "init_case",
                                "surface_fixable_by_rule": True,
                                "surface_rule_id": "rule_simulate_error_injection_repair",
                                "post_rule_residual_stage": "stage_4_initialization_singularity",
                                "post_rule_residual_error_type": "simulate_error",
                                "post_rule_residual_reason": "initialization failed",
                                "preview_admission": True,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = build_v0_3_13_seed_taskset(
                audit_summary_path=str(audit),
                preview_summary_path=str(preview),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["task_count"], 2)
            self.assertEqual(payload["family_counts"][FAMILY_RUNTIME], 1)
            self.assertEqual(payload["family_counts"][FAMILY_INITIALIZATION], 1)


if __name__ == "__main__":
    unittest.main()
