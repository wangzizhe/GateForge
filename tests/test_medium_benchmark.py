import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MediumBenchmarkTests(unittest.TestCase):
    def test_medium_benchmark_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack = root / "pack.json"
            pack.write_text(
                json.dumps(
                    {
                        "pack_id": "medium_mock_pack",
                        "cases": [
                            {
                                "name": "mock_pass",
                                "backend": "mock",
                                "expected": {
                                    "gate": "PASS",
                                    "failure_type": "none",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                },
                            },
                            {
                                "name": "mock_fail_expected",
                                "backend": "mock",
                                "expected": {
                                    "gate": "FAIL",
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            summary = root / "summary.json"
            report = root / "summary.md"
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark",
                    "--pack",
                    str(pack),
                    "--out-dir",
                    str(out_dir),
                    "--summary-out",
                    str(summary),
                    "--report-out",
                    str(report),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["pack_id"], "medium_mock_pack")
            self.assertEqual(payload["total_cases"], 2)
            self.assertEqual(payload["pass_count"], 1)
            self.assertEqual(payload["fail_count"], 1)
            self.assertEqual(payload["pass_rate"], 0.5)
            self.assertEqual(payload["mismatch_case_count"], 1)
            self.assertIn("none", payload["failure_type_distribution"])

    def test_medium_pack_v1_contains_expected_cases(self) -> None:
        payload = json.loads(Path("benchmarks/medium_pack_v1.json").read_text(encoding="utf-8"))
        names = {c.get("name") for c in payload.get("cases", [])}
        self.assertIn("medium_pass_default_1", names)
        self.assertIn("medium_pass_short_1", names)
        self.assertIn("medium_pass_long_1", names)
        self.assertIn("medium_fail_parse_1", names)
        self.assertIn("medium_fail_model_check_1", names)
        self.assertIn("medium_fail_simulate_1", names)
        self.assertEqual(len(payload.get("cases", [])), 12)


if __name__ == "__main__":
    unittest.main()
