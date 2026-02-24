import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutationMetricsTests(unittest.TestCase):
    def test_metrics_computation_outputs_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            summary = root / "summary.json"
            out = root / "metrics.json"
            manifest.write_text(
                json.dumps(
                    {
                        "pack_id": "mutation_pack_v1",
                        "pack_version": "v1",
                        "backend": "mock",
                        "cases": [
                            {"name": "c1", "expected": {"failure_type": "none"}},
                            {"name": "c2", "expected": {"failure_type": "script_parse_error"}},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            summary.write_text(
                json.dumps(
                    {
                        "total_cases": 2,
                        "pass_count": 1,
                        "cases": [
                            {"name": "c1", "result": "PASS", "failure_type": "none"},
                            {"name": "c2", "result": "FAIL", "failure_type": "model_check_error"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutation_metrics",
                    "--manifest",
                    str(manifest),
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
            self.assertEqual(payload.get("pack_id"), "mutation_pack_v1")
            self.assertEqual(payload.get("pack_version"), "v1")
            self.assertAlmostEqual(float(payload.get("gate_pass_rate", 0.0)), 0.5)
            self.assertAlmostEqual(float(payload.get("expected_vs_actual_match_rate", 0.0)), 0.5)
            self.assertIsInstance(payload.get("failure_type_distribution"), dict)


if __name__ == "__main__":
    unittest.main()
