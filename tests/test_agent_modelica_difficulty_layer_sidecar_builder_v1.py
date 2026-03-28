import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_difficulty_layer_sidecar_builder_v1 import build_sidecar


class AgentModelicaDifficultyLayerSidecarBuilderV1Tests(unittest.TestCase):
    def test_build_sidecar_uses_observed_override_for_hardpack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mutant = root / "mutant.mo"
            mutant.write_text("model M\nReal x=__gf_undef_1;\nend M;\n", encoding="utf-8")
            substrate = root / "hardpack.json"
            substrate.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "model_check_error",
                                "mutated_model_path": str(mutant),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results = root / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "m1",
                                "resolution_attribution": {
                                    "dominant_stage_subtype": "stage_3_behavioral_contract_semantic"
                                }
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_sidecar = root / "sidecar.json"
            summary = build_sidecar(
                substrate_path=str(substrate),
                results_paths=[str(results)],
                out_sidecar=str(out_sidecar),
            )
            payload = json.loads(out_sidecar.read_text(encoding="utf-8"))
            row = payload["annotations"][0]
            self.assertEqual(row["difficulty_layer"], "layer_3")
            self.assertEqual(row["difficulty_layer_source"], "observed")
            self.assertEqual(summary["observed_count"], 1)
            self.assertEqual(summary["inferred_count"], 0)

    def test_build_sidecar_falls_back_to_inferred_for_taskset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            substrate = root / "taskset.json"
            substrate.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "failure_type": "switch_then_recovery",
                                "multi_step_family": "switch_then_recovery",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_sidecar = root / "sidecar.json"
            summary = build_sidecar(
                substrate_path=str(substrate),
                results_paths=[],
                out_sidecar=str(out_sidecar),
            )
            payload = json.loads(out_sidecar.read_text(encoding="utf-8"))
            row = payload["annotations"][0]
            self.assertEqual(row["difficulty_layer"], "layer_3")
            self.assertEqual(row["difficulty_layer_source"], "inferred")
            self.assertEqual(row["expected_layer_reason"], "inferred_from_task_family")
            self.assertEqual(summary["observed_count"], 0)
            self.assertEqual(summary["inferred_count"], 1)


if __name__ == "__main__":
    unittest.main()
