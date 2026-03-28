import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


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
                cwd="/Users/meow/Documents/GateForge",
                env=env,
            )
            summary = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["total_items"], 1)
            self.assertEqual(summary["inferred_count"], 1)


if __name__ == "__main__":
    unittest.main()
