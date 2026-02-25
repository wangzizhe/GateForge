import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetQualityGateTests(unittest.TestCase):
    def test_quality_gate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build = root / "summary.json"
            quality = root / "quality.json"
            dist = root / "distribution.json"
            out = root / "gate.json"

            build.write_text(
                json.dumps(
                    {
                        "total_cases": 120,
                        "deduplicated_cases": 114,
                        "dropped_duplicate_cases": 6,
                    }
                ),
                encoding="utf-8",
            )
            quality.write_text(
                json.dumps(
                    {
                        "oracle_match_rate": 0.91,
                        "replay_stable_rate": 0.99,
                    }
                ),
                encoding="utf-8",
            )
            dist.write_text(
                json.dumps(
                    {
                        "actual_failure_type": {
                            "none": 40,
                            "simulate_error": 30,
                            "model_check_error": 20,
                            "script_parse_error": 15,
                            "runtime_regression": 9,
                        }
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_quality_gate",
                    "--build-summary",
                    str(build),
                    "--quality",
                    str(quality),
                    "--distribution",
                    str(dist),
                    "--out",
                    str(out),
                    "--min-total-cases",
                    "100",
                    "--min-failure-type-coverage",
                    "4",
                    "--min-oracle-match-rate",
                    "0.7",
                    "--min-replay-stable-rate",
                    "0.95",
                    "--max-duplicate-rate",
                    "0.1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")

    def test_quality_gate_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build = root / "summary.json"
            quality = root / "quality.json"
            dist = root / "distribution.json"
            out = root / "gate.json"

            build.write_text(
                json.dumps(
                    {
                        "total_cases": 10,
                        "deduplicated_cases": 7,
                        "dropped_duplicate_cases": 3,
                    }
                ),
                encoding="utf-8",
            )
            quality.write_text(
                json.dumps(
                    {
                        "oracle_match_rate": 0.4,
                        "replay_stable_rate": 0.7,
                    }
                ),
                encoding="utf-8",
            )
            dist.write_text(
                json.dumps(
                    {
                        "actual_failure_type": {
                            "none": 9,
                            "simulate_error": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_quality_gate",
                    "--build-summary",
                    str(build),
                    "--quality",
                    str(quality),
                    "--distribution",
                    str(dist),
                    "--out",
                    str(out),
                    "--min-total-cases",
                    "100",
                    "--min-failure-type-coverage",
                    "4",
                    "--min-oracle-match-rate",
                    "0.7",
                    "--min-replay-stable-rate",
                    "0.95",
                    "--max-duplicate-rate",
                    "0.1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            checks = payload.get("checks", {})
            self.assertEqual(checks.get("min_total_cases"), "FAIL")
            self.assertEqual(checks.get("min_failure_type_coverage"), "FAIL")


if __name__ == "__main__":
    unittest.main()
