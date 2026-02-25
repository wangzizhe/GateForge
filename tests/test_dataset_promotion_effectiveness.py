import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionEffectivenessTests(unittest.TestCase):
    def test_keep_when_metrics_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before = root / "before.json"
            after = root / "after.json"
            out = root / "effectiveness.json"
            before.write_text(json.dumps({"pass_rate": 0.7, "needs_review_rate": 0.2, "fail_rate": 0.1}), encoding="utf-8")
            after.write_text(json.dumps({"pass_rate": 0.72, "needs_review_rate": 0.18, "fail_rate": 0.1}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_effectiveness",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "KEEP")
            self.assertEqual(payload.get("reasons"), [])

    def test_rollback_review_on_fail_rate_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before = root / "before.json"
            after = root / "after.json"
            out = root / "effectiveness.json"
            before.write_text(json.dumps({"pass_rate": 0.8, "needs_review_rate": 0.1, "fail_rate": 0.1}), encoding="utf-8")
            after.write_text(json.dumps({"pass_rate": 0.5, "needs_review_rate": 0.2, "fail_rate": 0.3}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_effectiveness",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "ROLLBACK_REVIEW")
            self.assertIn("promotion_apply_fail_rate_increase_too_high", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
