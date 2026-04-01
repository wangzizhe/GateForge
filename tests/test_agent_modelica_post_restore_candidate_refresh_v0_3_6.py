from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_post_restore_candidate_refresh_v0_3_6 import (
    refresh_post_restore_candidates,
)


def _protocol() -> dict:
    return {
        "protocol_version": "v0_3_6_single_sweep_baseline_authority_v1",
        "baseline_lever_name": "simulate_error_parameter_recovery_sweep",
        "baseline_reference_version": "v0.3.5",
        "enabled_policy_flags": {
            "allow_baseline_single_sweep": True,
            "allow_new_multistep_policy": False,
        },
    }


class AgentModelicaPostRestoreCandidateRefreshV036Tests(unittest.TestCase):
    def test_refresh_attaches_results_and_lane_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_refresh_") as td:
            root = Path(td)
            candidates = root / "candidates.json"
            results = root / "results.json"
            classifier = root / "classifier.json"
            candidates.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": f"case_{i}",
                                "v0_3_6_family_id": "post_restore_residual_semantic_conflict",
                                "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                                "dual_layer_mutation": True,
                                "declared_failure_type": "simulate_error",
                            }
                            for i in range(10)
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results.write_text(
                json.dumps(
                    {
                        "baseline_measurement_protocol": _protocol(),
                        "results": [
                            {
                                "task_id": f"case_{i}",
                                "resolution_path": "rule_then_llm",
                                "planner_invoked": True,
                                "rounds_used": 4,
                                "llm_request_count": 2,
                                "single_sweep_outcome": "residual_failure_after_first_correction",
                                "first_correction_success": True,
                                "residual_failure_after_first_correction": True,
                            }
                            for i in range(10)
                        ],
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": f"case_{i}",
                                "post_restore_failure_bucket": "residual_semantic_conflict_after_restore",
                                "post_restore_bucket_reasons": ["residual"],
                            }
                            for i in range(10)
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = refresh_post_restore_candidates(
                candidate_taskset_path=str(candidates),
                results_path=str(results),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["metrics"]["matched_result_count"], 10)
            self.assertEqual(payload["metrics"]["matched_classifier_count"], 10)
            self.assertEqual((payload["lane_summary"] or {}).get("lane_status"), "FREEZE_READY")
            first = payload["tasks"][0]
            self.assertEqual(first["post_restore_failure_bucket"], "residual_semantic_conflict_after_restore")
            self.assertEqual(first["single_sweep_outcome"], "residual_failure_after_first_correction")

    def test_refresh_uses_top_level_protocol_if_row_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_refresh_proto_") as td:
            root = Path(td)
            candidates = root / "candidates.json"
            results = root / "results.json"
            candidates.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "case_a",
                                "v0_3_6_family_id": "post_restore_residual_semantic_conflict",
                                "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                                "dual_layer_mutation": True,
                                "declared_failure_type": "simulate_error",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results.write_text(
                json.dumps(
                    {
                        "baseline_measurement_protocol": _protocol(),
                        "results": [
                            {
                                "task_id": "case_a",
                                "resolution_path": "rule_then_llm",
                                "planner_invoked": True,
                                "single_sweep_outcome": "residual_failure_after_first_correction",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload = refresh_post_restore_candidates(
                candidate_taskset_path=str(candidates),
                results_path=str(results),
                out_dir=str(root / "out"),
            )
            protocol = payload["tasks"][0]["baseline_measurement_protocol"]
            self.assertEqual(protocol["protocol_version"], "v0_3_6_single_sweep_baseline_authority_v1")


if __name__ == "__main__":
    unittest.main()
