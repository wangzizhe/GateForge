import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MediumBenchmarkAnalyzeTests(unittest.TestCase):
    def test_analyze_handles_empty_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary = root / "summary.json"
            out = root / "analysis.json"
            summary.write_text(
                json.dumps(
                    {
                        "pack_id": "medium_pack_v1",
                        "total_cases": 12,
                        "mismatch_case_count": 0,
                        "mismatch_cases": [],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_analyze",
                    "--summary",
                    str(summary),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("mismatch_case_count"), 0)
            self.assertEqual(payload.get("mismatch_key_counts"), {})
            self.assertEqual(payload.get("recommendations"), [])

    def test_analyze_groups_mismatch_keys_and_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary = root / "summary.json"
            out = root / "analysis.json"
            summary.write_text(
                json.dumps(
                    {
                        "pack_id": "medium_pack_v1",
                        "total_cases": 12,
                        "mismatch_case_count": 2,
                        "mismatch_cases": [
                            {
                                "name": "c1",
                                "mismatches": [
                                    "failure_type:expected=none,actual=docker_error",
                                    "check_ok:expected=True,actual=False",
                                ],
                            },
                            {
                                "name": "c2",
                                "mismatches": [
                                    "failure_type:expected=none,actual=docker_error",
                                    "simulate_ok:expected=True,actual=False",
                                ],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_analyze",
                    "--summary",
                    str(summary),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            counts = payload.get("mismatch_key_counts", {})
            self.assertEqual(counts.get("failure_type"), 2)
            self.assertEqual(counts.get("check_ok"), 1)
            self.assertEqual(counts.get("simulate_ok"), 1)
            recs = payload.get("recommendations", [])
            self.assertTrue(recs)
            self.assertEqual(recs[0].get("mismatch_key"), "failure_type")
            self.assertEqual(recs[0].get("priority"), "P0")


if __name__ == "__main__":
    unittest.main()
