from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_primary_slice_v0_3_3 import (
    build_primary_slice,
    run_primary_slice,
)


class AgentModelicaTrackCPrimarySliceV033Tests(unittest.TestCase):
    def test_build_primary_slice_excludes_frozen_and_seed_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_slice_") as td:
            root = Path(td)
            candidates = root / "candidates.json"
            frozen_track_a = root / "track_a.json"
            frozen_seed = root / "seed.json"

            candidates.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "seed_case",
                                "classification": "freeze_ready_observed",
                                "selection_reasons": [
                                    "observed_resolution_path:llm_planner_assisted",
                                    "planner_invoked_observed",
                                ],
                            },
                            {
                                "task_id": "new_case",
                                "v0_3_family_id": "runtime_numerical_instability",
                                "expected_layer_hint": "layer_4",
                                "resolution_path": "llm_planner_assisted",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            frozen_track_a.write_text(json.dumps({"cases": [{"mutation_id": "track_a_case"}]}), encoding="utf-8")
            frozen_seed.write_text(json.dumps({"tasks": [{"task_id": "seed_case"}]}), encoding="utf-8")

            payload = build_primary_slice(
                candidate_taskset_path=str(candidates),
                frozen_references=[
                    {"ref_id": "track_a_valid32", "path": str(frozen_track_a)},
                    {"ref_id": "v0_3_2_seed_slice", "path": str(frozen_seed)},
                ],
                min_primary_slice_cases=1,
            )
            admitted_ids = [row["item_id"] for row in payload["admitted_rows"]]
            excluded_lookup = {row["item_id"]: row for row in payload["excluded_rows"]}

            self.assertEqual(admitted_ids, ["new_case"])
            self.assertIn("seed_case", excluded_lookup)
            self.assertIn("frozen_hit:v0_3_2_seed_slice", excluded_lookup["seed_case"]["gate_reasons"]["holdout_clean"])

    def test_initialization_singularity_requires_layer4_observed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_init_") as td:
            root = Path(td)
            candidates = root / "candidates.json"
            candidates.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "init_l2",
                                "v0_3_family_id": "initialization_singularity",
                                "expected_layer_hint": "layer_2",
                                "resolution_path": "rule_then_llm",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_primary_slice(
                candidate_taskset_path=str(candidates),
                frozen_references=[],
                min_primary_slice_cases=1,
            )
            self.assertEqual(payload["metrics"]["admitted_count"], 0)
            self.assertEqual(payload["metrics"]["family_blocked_count"], 1)

    def test_build_primary_slice_marks_primary_ready_when_thresholds_hold(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_ready_") as td:
            root = Path(td)
            candidates = root / "candidates.json"
            tasks = []
            for idx in range(20):
                tasks.append(
                    {
                        "task_id": f"cand_{idx}",
                        "v0_3_family_id": "hard_multiround_simulate_failure",
                        "expected_layer_hint": "layer_4",
                        "resolution_path": "llm_planner_assisted",
                    }
                )
            candidates.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
            payload = build_primary_slice(
                candidate_taskset_path=str(candidates),
                frozen_references=[],
                min_primary_slice_cases=20,
                min_planner_sensitive_pct=70.0,
                max_deterministic_only_pct=30.0,
            )
            self.assertEqual(payload["status"], "PRIMARY_READY")
            self.assertEqual(payload["metrics"]["admitted_count"], 20)
            self.assertEqual(payload["metrics"]["deterministic_only_pct"], 0.0)

    def test_run_primary_slice_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_run_") as td:
            root = Path(td)
            candidates = root / "candidates.json"
            candidates.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "cand_0",
                                "v0_3_family_id": "runtime_numerical_instability",
                                "expected_layer_hint": "layer_4",
                                "resolution_path": "rule_then_llm",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = run_primary_slice(
                candidate_taskset_path=str(candidates),
                out_dir=str(root / "out"),
                frozen_references=[],
                min_primary_slice_cases=1,
            )
            self.assertEqual(payload["status"], "PRIMARY_READY")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "summary.md").exists())
            self.assertTrue((root / "out" / "taskset_frozen.json").exists())
            self.assertTrue((root / "out" / "taskset_frozen_candidate.json").exists())
            self.assertEqual(payload["taskset_frozen_path"], str((root / "out" / "taskset_frozen.json").resolve()))


if __name__ == "__main__":
    unittest.main()
