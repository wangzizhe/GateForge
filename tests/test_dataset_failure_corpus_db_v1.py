import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureCorpusDbV1Tests(unittest.TestCase):
    def test_db_v1_builds_normalized_cases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            defaults = root / "defaults.json"
            db_out = root / "db.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps(
                    [
                        {
                            "corpus_case_id": "fc-1",
                            "fingerprint": "f1",
                            "model_scale": "medium",
                            "failure_type": "numerical_divergence",
                            "failure_stage": "simulation",
                            "severity": "high",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            defaults.write_text(
                json.dumps(
                    {
                        "simulator_version": "openmodelica-1.25.5",
                        "seed": 7,
                        "scenario_hash": "x",
                        "repro_command": "run demo",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_db_v1",
                    "--failure-corpus-registry",
                    str(registry),
                    "--repro-defaults",
                    str(defaults),
                    "--db-out",
                    str(db_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            db = json.loads(db_out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(db.get("schema_version"), "failure_corpus_db_v1")
            self.assertEqual(len(db.get("cases", [])), 1)
            self.assertIn("reproducibility", db["cases"][0])

    def test_db_v1_fails_when_registry_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_db_v1",
                    "--failure-corpus-registry",
                    str(root / "missing.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
