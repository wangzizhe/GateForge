import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_layer4_holdout_v0_3_1 import build_layer4_holdout_v0_3_1


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaLayer4HoldoutV031Tests(unittest.TestCase):
    def test_build_holdout_from_v0_3_0_lane_split(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_taskset = root / "source_taskset.json"
            source_sidecar = root / "source_sidecar.json"
            base_spec = root / "base_spec.json"
            base_summary = root / "base_summary.json"
            _write_json(
                source_taskset,
                {
                    "tasks": [
                        {"task_id": "t1", "split": "holdout", "v0_3_family_id": "initialization_singularity"},
                        {"task_id": "t2", "split": "train", "v0_3_family_id": "runtime_numerical_instability"},
                        {"task_id": "t3", "split": "holdout", "v0_3_family_id": "hard_multiround_simulate_failure"},
                    ]
                },
            )
            _write_json(
                source_sidecar,
                {
                    "annotations": [
                        {"item_id": "t1", "difficulty_layer": "layer_4", "difficulty_layer_source": "override"},
                        {"item_id": "t2", "difficulty_layer": "layer_4", "difficulty_layer_source": "override"},
                        {"item_id": "t3", "difficulty_layer": "layer_4", "difficulty_layer_source": "override"},
                    ]
                },
            )
            _write_json(base_spec, {"lanes": [{"lane_id": "base", "sidecar": str(source_sidecar)}]})
            _write_json(base_summary, {"coverage_gap": {"aggregate_layer_counts": {"layer_4": 3}}})
            payload = build_layer4_holdout_v0_3_1(
                out_dir=str(root / "out"),
                source_taskset_path=str(source_taskset),
                source_sidecar_path=str(source_sidecar),
                base_spec_path=str(base_spec),
                base_summary_path=str(base_summary),
            )
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("task_count") or 0), 2)
            self.assertEqual(int(payload["coverage_delta"]["layer4_case_count_delta"]), 2)


if __name__ == "__main__":
    unittest.main()
