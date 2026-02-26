import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureCorpusIngestBridgeV1Tests(unittest.TestCase):
    def test_ingest_bridge_adds_stable_cases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            stability = root / "stability.json"
            obs = root / "obs.json"
            existing = root / "existing.json"
            db_out = root / "db_out.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_manifest_v1",
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "target_model_id": "mdl_large",
                                "target_scale": "large",
                                "seed": 11,
                                "repro_command": "run m1",
                            },
                            {
                                "mutation_id": "m2",
                                "target_model_id": "mdl_medium",
                                "target_scale": "medium",
                                "seed": 12,
                                "repro_command": "run m2",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stability.write_text(
                json.dumps({"status": "PASS", "unstable_mutations": [{"mutation_id": "m2"}]}),
                encoding="utf-8",
            )
            obs.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "observed_failure_types": ["simulate_error", "simulate_error", "simulate_error"]},
                            {"mutation_id": "m2", "observed_failure_types": ["semantic_regression", "simulate_error", "semantic_regression"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            existing.write_text(json.dumps({"schema_version": "failure_corpus_db_v1", "cases": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_ingest_bridge_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--repro-stability-summary",
                    str(stability),
                    "--replay-observations",
                    str(obs),
                    "--existing-failure-corpus-db",
                    str(existing),
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
            self.assertEqual(int(summary.get("ingested_cases", 0)), 1)
            self.assertEqual(int(summary.get("skipped_unstable_cases", 0)), 1)

    def test_ingest_bridge_fails_without_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_ingest_bridge_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--repro-stability-summary",
                    str(root / "missing_stability.json"),
                    "--replay-observations",
                    str(root / "missing_obs.json"),
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
