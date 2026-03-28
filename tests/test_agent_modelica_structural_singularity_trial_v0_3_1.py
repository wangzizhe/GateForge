import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_structural_singularity_trial_v0_3_1 import build_structural_singularity_trial


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaStructuralSingularityTrialV031Tests(unittest.TestCase):
    def test_trial_rejects_current_program_when_taxonomy_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            family_spec = root / "family_spec.json"
            _write_json(
                family_spec,
                {
                    "families": [
                        {
                            "family_id": "structural_singularity",
                            "expected_layer_hint": "layer_4",
                            "viability_status": "deferred_v0_3_1",
                        }
                    ]
                },
            )
            source = root / "source.mo"
            mutated = root / "mutant.mo"
            source.write_text("model A end A;", encoding="utf-8")
            mutated.write_text("model A end A;", encoding="utf-8")
            under = root / "under.json"
            over = root / "over.json"
            _write_json(
                under,
                {
                    "tasks": [
                        {
                            "task_id": "u1",
                            "failure_type": "underconstrained_system",
                            "source_model_path": str(source),
                            "mutated_model_path": str(mutated),
                        }
                    ]
                },
            )
            _write_json(
                over,
                {
                    "tasks": [
                        {
                            "task_id": "o1",
                            "failure_type": "overconstrained_system",
                            "source_model_path": str(source),
                            "mutated_model_path": str(mutated),
                        }
                    ]
                },
            )
            under_fast_check = root / "under_fast_check.json"
            _write_json(
                under_fast_check,
                {
                    "status": "PASS",
                    "total_tasks": 1,
                    "pass_count": 1,
                    "stage_match_rate_pct": 100.0,
                },
            )
            payload = build_structural_singularity_trial(
                out_dir=str(root / "out"),
                family_spec_path=str(family_spec),
                under_taskset_path=str(under),
                under_fast_check_path=str(under_fast_check),
                over_taskset_path=str(over),
            )
            self.assertEqual(payload.get("decision"), "rejected_for_current_benchmark_program")
            self.assertFalse(bool(payload.get("official_micro_lane_created")))


if __name__ == "__main__":
    unittest.main()
