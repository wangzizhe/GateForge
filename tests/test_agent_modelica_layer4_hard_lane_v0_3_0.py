import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_layer4_hard_lane_v0_3_0 import build_layer4_hard_lane


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaLayer4HardLaneV030Tests(unittest.TestCase):
    def test_build_layer4_hard_lane_combines_families_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            family_spec = root / "family_spec.json"
            _write_json(
                family_spec,
                {
                    "families": [
                        {
                            "family_id": "initialization_singularity",
                            "enabled_for_v0_3_0": True,
                            "validation_criterion": {
                                "min_observed_layer4_share_pct": 60.0,
                                "max_gateforge_success_rate_pct": 85.0,
                            },
                        },
                        {
                            "family_id": "runtime_numerical_instability",
                            "enabled_for_v0_3_0": True,
                            "validation_criterion": {
                                "min_observed_layer4_share_pct": 60.0,
                                "min_stage4_stage5_share_pct": 50.0,
                            },
                        },
                        {
                            "family_id": "hard_multiround_simulate_failure",
                            "enabled_for_v0_3_0": True,
                            "validation_criterion": {
                                "min_observed_layer4_share_pct": 60.0,
                                "min_hard_case_rate_pct": 40.0,
                            },
                        },
                    ]
                },
            )
            init_taskset = root / "init" / "taskset_frozen.json"
            _write_json(
                init_taskset,
                {
                    "tasks": [
                        {"task_id": "init_a", "failure_type": "initialization_infeasible", "mock_success_round": 2},
                        {"task_id": "init_b", "failure_type": "initialization_infeasible", "mock_success_round": 2},
                    ]
                },
            )
            init_results = root / "init" / "results.json"
            _write_json(
                init_results,
                {"records": [{"task_id": "init_a", "passed": True}, {"task_id": "init_b", "passed": False}]},
            )
            runtime_taskset = root / "runtime" / "taskset_frozen.json"
            _write_json(
                runtime_taskset,
                {
                    "tasks": [
                        {"task_id": "rt_a", "failure_type": "solver_sensitive_simulate_failure", "mock_success_round": 2},
                        {"task_id": "rt_b", "failure_type": "solver_sensitive_simulate_failure", "mock_success_round": 2},
                    ]
                },
            )
            multiround_taskset = root / "multiround" / "taskset_frozen.json"
            _write_json(
                multiround_taskset,
                {
                    "tasks": [
                        {"task_id": "mr_a", "failure_type": "cascading_structural_failure", "expected_rounds_min": 2, "cascade_depth": 2},
                        {"task_id": "mr_b", "failure_type": "coupled_conflict_failure", "expected_rounds_min": 2, "cascade_depth": 2},
                    ]
                },
            )
            out_dir = root / "out"
            summary = build_layer4_hard_lane(
                family_spec_path=str(family_spec),
                out_dir=str(out_dir),
                source_specs=[
                    {
                        "family_id": "initialization_singularity",
                        "source_taskset_path": str(init_taskset),
                        "results_paths": [str(init_results)],
                        "failure_types": ["initialization_infeasible"],
                        "difficulty_layer": "layer_4",
                        "dominant_stage_subtype": "stage_4_initialization_singularity",
                        "layer_reason": "manual_family_review_initialization_singularity",
                    },
                    {
                        "family_id": "runtime_numerical_instability",
                        "source_taskset_path": str(runtime_taskset),
                        "failure_types": ["solver_sensitive_simulate_failure"],
                        "difficulty_layer": "layer_4",
                        "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                        "layer_reason": "manual_family_review_runtime_numerical_instability",
                    },
                    {
                        "family_id": "hard_multiround_simulate_failure",
                        "source_taskset_path": str(multiround_taskset),
                        "failure_types": [],
                        "difficulty_layer": "layer_4",
                        "layer_reason": "manual_family_review_hard_multiround",
                    },
                ],
            )
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("task_count") or 0), 6)
            taskset_payload = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(int(taskset_payload.get("task_count") or 0), 6)
            sidecar_payload = json.loads((out_dir / "layer_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(int(sidecar_payload["summary"]["override_count"]), 6)
            family_rows = {row["family_id"]: row for row in summary.get("family_summaries") or []}
            self.assertEqual(family_rows["initialization_singularity"]["gateforge_success_rate_pct"], 50.0)
            self.assertEqual(family_rows["hard_multiround_simulate_failure"]["hard_case_rate_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
