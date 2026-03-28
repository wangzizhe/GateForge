from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_foundation_acceptance_v0 import build_summary


class AgentModelicaFoundationAcceptanceV0Tests(unittest.TestCase):
    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_build_summary_passes_when_all_checks_are_met(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            track_a_results = root / "track_a_results.json"
            planner_results = root / "planner_results.json"
            layer_summary = root / "layer_summary.json"
            track_a_sidecar = root / "track_a_sidecar.json"
            planner_sidecar = root / "planner_sidecar.json"
            regen_path = root / "regen_source.json"

            self._write_json(
                track_a_results,
                {
                    "records": [
                        {
                            "task_id": "a1",
                            "passed": True,
                            "dominant_stage_subtype": "stage_2_structural_balance_reference",
                            "resolution_path": "deterministic_rule_only",
                            "planner_invoked": False,
                        },
                        {
                            "task_id": "a2",
                            "passed": True,
                            "dominant_stage_subtype": "stage_3_behavioral_contract_semantic",
                            "resolution_path": "rule_then_llm",
                            "planner_invoked": True,
                            "llm_request_count_delta": 1,
                            "llm_plan_generated": True,
                        },
                    ]
                },
            )
            self._write_json(
                planner_results,
                {
                    "records": [
                        {
                            "task_id": "p1",
                            "passed": True,
                            "dominant_stage_subtype": "stage_4_initialization_singularity",
                            "resolution_path": "llm_planner_assisted",
                            "planner_invoked": True,
                            "llm_request_count_delta": 1,
                            "llm_plan_generated": True,
                            "llm_plan_used": True,
                        },
                        {
                            "task_id": "p2",
                            "passed": True,
                            "dominant_stage_subtype": "stage_3_behavioral_contract_semantic",
                            "resolution_path": "rule_then_llm",
                            "planner_invoked": True,
                            "llm_request_count_delta": 1,
                            "llm_plan_generated": True,
                        },
                    ]
                },
            )
            self._write_json(
                layer_summary,
                {
                    "coverage_gap": {
                        "aggregate_layer_counts": {
                            "layer_1": 6,
                            "layer_2": 4,
                            "layer_3": 3,
                            "layer_4": 2,
                        }
                    }
                },
            )
            self._write_json(track_a_sidecar, {"annotations": []})
            self._write_json(planner_sidecar, {"annotations": []})
            self._write_json(regen_path, {"status": "PASS"})

            summary = build_summary(
                {
                    "layer_summary": str(layer_summary),
                    "required_regeneration_paths": [str(regen_path)],
                    "lanes": [
                        {
                            "lane_id": "track_a",
                            "run_results": str(track_a_results),
                            "sidecar": str(track_a_sidecar),
                            "planner_expected": False,
                        },
                        {
                            "lane_id": "planner_sensitive",
                            "run_results": str(planner_results),
                            "sidecar": str(planner_sidecar),
                            "planner_expected": True,
                        },
                    ],
                    "thresholds": {
                        "min_stage_subtype_coverage_pct": 95.0,
                        "max_unresolved_success_count": 0,
                        "min_planner_invoked_rate_pct_when_expected": 50.0,
                        "max_layer4_share_pct": 20.0,
                    },
                }
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["checks"]["dominant_stage_subtype_coverage"]["status"], "PASS")
            self.assertEqual(summary["checks"]["planner_sensitive_activation"]["status"], "PASS")
            self.assertEqual(summary["checks"]["layer_4_scarcity_confirmation"]["status"], "PASS")

    def test_build_summary_fails_on_unresolved_success_and_planner_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planner_results = root / "planner_results.json"
            layer_summary = root / "layer_summary.json"
            planner_sidecar = root / "planner_sidecar.json"

            self._write_json(
                planner_results,
                {
                    "records": [
                        {
                            "task_id": "p1",
                            "passed": True,
                            "dominant_stage_subtype": "stage_4_initialization_singularity",
                            "resolution_path": "unresolved",
                            "planner_invoked": False,
                            "llm_request_count_delta": 0,
                        }
                    ]
                },
            )
            self._write_json(
                layer_summary,
                {
                    "coverage_gap": {
                        "aggregate_layer_counts": {
                            "layer_1": 1,
                            "layer_4": 3,
                        }
                    }
                },
            )
            self._write_json(planner_sidecar, {"annotations": []})

            summary = build_summary(
                {
                    "layer_summary": str(layer_summary),
                    "required_regeneration_paths": [str(root / "missing.json")],
                    "lanes": [
                        {
                            "lane_id": "planner_sensitive",
                            "run_results": str(planner_results),
                            "sidecar": str(planner_sidecar),
                            "planner_expected": True,
                        }
                    ],
                    "thresholds": {
                        "min_stage_subtype_coverage_pct": 95.0,
                        "max_unresolved_success_count": 0,
                        "min_planner_invoked_rate_pct_when_expected": 50.0,
                        "max_layer4_share_pct": 50.0,
                    },
                }
            )

            self.assertEqual(summary["status"], "FAIL")
            self.assertIn("planner_sensitive_activation_not_pass", summary["reasons"])
            self.assertIn("regeneration_path_presence_not_pass", summary["reasons"])
            self.assertIn("layer_4_scarcity_confirmation_not_pass", summary["reasons"])
            self.assertEqual(summary["lanes"][0]["saved_vs_recomputed_mismatch_count"], 1)


if __name__ == "__main__":
    unittest.main()
