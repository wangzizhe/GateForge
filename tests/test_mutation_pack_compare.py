import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutationPackCompareTests(unittest.TestCase):
    def test_compare_pass_when_candidate_not_worse(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "summary.json"
            baseline.write_text(json.dumps({"pack_id": "v0", "expected_vs_actual_match_rate": 0.8}), encoding="utf-8")
            candidate.write_text(json.dumps({"pack_id": "v1", "expected_vs_actual_match_rate": 0.9}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutation_pack_compare",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "PASS")
            self.assertGreater(float(payload.get("delta_match_rate", 0.0)), 0.0)

    def test_compare_fail_on_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "summary.json"
            baseline.write_text(json.dumps({"pack_id": "v0", "expected_vs_actual_match_rate": 1.0}), encoding="utf-8")
            candidate.write_text(json.dumps({"pack_id": "v1", "expected_vs_actual_match_rate": 0.95}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutation_pack_compare",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "FAIL")
            self.assertIn("expected_vs_actual_match_rate_regressed", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
