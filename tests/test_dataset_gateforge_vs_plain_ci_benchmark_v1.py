import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGateforgeVsPlainCiBenchmarkV1Tests(unittest.TestCase):
    def test_comparison_pass_when_gateforge_advantage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gf = root / "gf.json"
            pc = root / "pc.json"
            out = root / "summary.json"

            gf.write_text(json.dumps({"blocked_critical_count": 10, "escaped_critical_count": 1, "false_positive_rate": 0.05, "needs_review_count": 8}), encoding="utf-8")
            pc.write_text(json.dumps({"blocked_critical_count": 7, "escaped_critical_count": 3, "false_positive_rate": 0.07, "needs_review_count": 2}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_gateforge_vs_plain_ci_benchmark_v1",
                    "--gateforge-summary",
                    str(gf),
                    "--plain-ci-summary",
                    str(pc),
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
            self.assertEqual(summary.get("verdict"), "GATEFORGE_ADVANTAGE")

    def test_comparison_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_gateforge_vs_plain_ci_benchmark_v1",
                    "--gateforge-summary",
                    str(root / "missing_gf.json"),
                    "--plain-ci-summary",
                    str(root / "missing_pc.json"),
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
