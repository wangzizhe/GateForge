import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class RunAgentModelicaDifficultyLayerSummaryV1Tests(unittest.TestCase):
    def test_wrapper_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sidecar = root / "sidecar.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "annotations": [
                            {
                                "item_id": "m1",
                                "difficulty_layer": "layer_2",
                                "difficulty_layer_source": "observed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            spec = root / "spec.json"
            spec.write_text(json.dumps({"lanes": [{"lane_id": "track_a", "sidecar": str(sidecar)}]}), encoding="utf-8")
            env = os.environ.copy()
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SUMMARY_SPEC"] = str(spec)
            env["GATEFORGE_AGENT_DIFFICULTY_LAYER_SUMMARY_OUT"] = str(root / "out" / "summary.json")
            subprocess.run(
                ["bash", "scripts/run_agent_modelica_difficulty_layer_summary_v1.sh"],
                check=True,
                cwd=str(REPO_ROOT),
                env=env,
            )
            payload = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["lane_count"], 1)


if __name__ == "__main__":
    unittest.main()
