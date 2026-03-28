import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class RunAgentModelicaDifficultyLayerSidecarBuilderV1Tests(unittest.TestCase):
    def test_wrapper_builds_summary(self) -> None:
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
            env = os.environ.copy()
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_SUBSTRATE"] = str(substrate)
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OUT_DIR"] = str(root / "out")
            subprocess.run(
                ["bash", "scripts/run_agent_modelica_difficulty_layer_sidecar_builder_v1.sh"],
                check=True,
                cwd=str(REPO_ROOT),
                env=env,
            )
            summary = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["total_items"], 1)
            self.assertEqual(summary["inferred_count"], 1)

    def test_wrapper_accepts_custom_hint_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            substrate = root / "hardpack.json"
            substrate.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "semantic_regression",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            hint_rules = root / "hint_rules.json"
            hint_rules.write_text(
                json.dumps(
                    {
                        "failure_types": {
                            "semantic_regression": {
                                "layer": "layer_4",
                                "reason": "inferred_from_custom_failure_type"
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_SUBSTRATE"] = str(substrate)
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OUT_DIR"] = str(root / "out")
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_HINT_RULES"] = str(hint_rules)
            subprocess.run(
                ["bash", "scripts/run_agent_modelica_difficulty_layer_sidecar_builder_v1.sh"],
                check=True,
                cwd=str(REPO_ROOT),
                env=env,
            )
            sidecar = json.loads((root / "out" / "layer_metadata.json").read_text(encoding="utf-8"))
            row = sidecar["annotations"][0]
            self.assertEqual(row["difficulty_layer"], "layer_4")

    def test_wrapper_accepts_override_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            substrate = root / "hardpack.json"
            substrate.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "semantic_regression",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            override_path = root / "override.json"
            override_path.write_text(
                json.dumps(
                    {
                        "overrides": {
                            "m1": {
                                "difficulty_layer": "layer_4",
                                "layer_reason": "manual_initial_review"
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_SUBSTRATE"] = str(substrate)
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OUT_DIR"] = str(root / "out")
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OVERRIDE"] = str(override_path)
            subprocess.run(
                ["bash", "scripts/run_agent_modelica_difficulty_layer_sidecar_builder_v1.sh"],
                check=True,
                cwd=str(REPO_ROOT),
                env=env,
            )
            summary = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["override_count"], 1)


if __name__ == "__main__":
    unittest.main()
