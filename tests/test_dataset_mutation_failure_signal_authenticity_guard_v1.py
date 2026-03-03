import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationFailureSignalAuthenticityGuardV1Tests(unittest.TestCase):
    def test_guard_pass_with_strong_failure_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "expected_failure_type": "model_check_error"},
                            {"mutation_id": "m3", "expected_failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            raw.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "execution_status": "EXECUTED", "final_return_code": 2, "attempts": [{"stderr": ""}]},
                            {"mutation_id": "m2", "execution_status": "EXECUTED", "final_return_code": 0, "attempts": [{"stderr": "assert failed"}]},
                            {"mutation_id": "m3", "execution_status": "EXECUTED", "final_return_code": 0, "attempts": [{"stderr": ""}]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_failure_signal_authenticity_guard_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
                    "--min-failure-signal-ratio-pct",
                    "50",
                    "--min-expected-failure-type-signal-coverage-pct",
                    "50",
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
            self.assertGreaterEqual(float(payload.get("failure_signal_ratio_pct", 0.0)), 50.0)

    def test_guard_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_failure_signal_authenticity_guard_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--mutation-raw-observations",
                    str(root / "missing_raw.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
