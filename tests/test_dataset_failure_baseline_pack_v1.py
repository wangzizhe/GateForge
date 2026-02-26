import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureBaselinePackV1Tests(unittest.TestCase):
    def test_baseline_pack_builds_selected_cases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = root / "db.json"
            pack = root / "pack.json"
            out = root / "summary.json"

            db.write_text(
                json.dumps(
                    {
                        "schema_version": "failure_corpus_db_v1",
                        "cases": [
                            {"case_id": "s1", "model_scale": "small", "failure_type": "a", "failure_stage": "x", "severity": "low", "fingerprint": "f1", "reproducibility": {"simulator_version": "v", "seed": 1, "scenario_hash": "h", "repro_command": "c"}},
                            {"case_id": "m1", "model_scale": "medium", "failure_type": "b", "failure_stage": "x", "severity": "medium", "fingerprint": "f2", "reproducibility": {"simulator_version": "v", "seed": 1, "scenario_hash": "h", "repro_command": "c"}},
                            {"case_id": "m2", "model_scale": "medium", "failure_type": "c", "failure_stage": "x", "severity": "high", "fingerprint": "f3", "reproducibility": {"simulator_version": "v", "seed": 1, "scenario_hash": "h", "repro_command": "c"}},
                            {"case_id": "l1", "model_scale": "large", "failure_type": "d", "failure_stage": "x", "severity": "high", "fingerprint": "f4", "reproducibility": {"simulator_version": "v", "seed": 1, "scenario_hash": "h", "repro_command": "c"}},
                            {"case_id": "l2", "model_scale": "large", "failure_type": "e", "failure_stage": "x", "severity": "critical", "fingerprint": "f5", "reproducibility": {"simulator_version": "v", "seed": 1, "scenario_hash": "h", "repro_command": "c"}}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_baseline_pack_v1",
                    "--failure-corpus-db",
                    str(db),
                    "--small-quota",
                    "1",
                    "--medium-quota",
                    "2",
                    "--large-quota",
                    "2",
                    "--pack-out",
                    str(pack),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("total_selected_cases"), 5)

    def test_baseline_pack_fail_missing_db(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_baseline_pack_v1",
                    "--failure-corpus-db",
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
