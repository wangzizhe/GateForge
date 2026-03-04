import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaFailureRepairCorpusV1Tests(unittest.TestCase):
    def test_build_failure_repair_corpus_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            out = root / "corpus.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "target_scale": "small",
                                "expected_failure_type": "model_check_error",
                                "expected_stage": "check",
                                "mutated_model_path": "a.mo",
                            },
                            {
                                "mutation_id": "m2",
                                "target_scale": "large",
                                "expected_failure_type": "semantic_regression",
                                "expected_stage": "simulate",
                                "mutated_model_path": "b.mo",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_failure_repair_corpus_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("row_count", 0)), 2)
            self.assertIn("model_check_error", payload.get("failure_type_distribution", {}))
            self.assertIn("semantic_regression", payload.get("failure_type_distribution", {}))


if __name__ == "__main__":
    unittest.main()
