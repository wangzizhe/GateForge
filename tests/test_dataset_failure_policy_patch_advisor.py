import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailurePolicyPatchAdvisorTests(unittest.TestCase):
    def test_advisor_recommends_tightening_when_signals_bad(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taxonomy = root / "taxonomy.json"
            benchmark = root / "benchmark.json"
            ladder = root / "ladder.json"
            out = root / "advisor.json"
            taxonomy.write_text(
                json.dumps({"missing_failure_types": ["stability_regression"], "missing_model_scales": ["large"]}),
                encoding="utf-8",
            )
            benchmark.write_text(
                json.dumps(
                    {
                        "detection_rate_after": 0.72,
                        "false_positive_rate_after": 0.14,
                        "regression_rate_after": 0.24,
                        "distribution_drift_score": 0.4,
                    }
                ),
                encoding="utf-8",
            )
            ladder.write_text(json.dumps({"large_ready": False}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_policy_patch_advisor",
                    "--failure-taxonomy-coverage",
                    str(taxonomy),
                    "--failure-distribution-benchmark",
                    str(benchmark),
                    "--model-scale-ladder",
                    str(ladder),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice") or {}
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertEqual(advice.get("suggested_policy_profile"), "dataset_strict")
            self.assertEqual(advice.get("suggested_action"), "tighten_thresholds_and_require_large_review")

    def test_advisor_recommends_keep_when_signals_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taxonomy = root / "taxonomy.json"
            benchmark = root / "benchmark.json"
            ladder = root / "ladder.json"
            out = root / "advisor.json"
            taxonomy.write_text(json.dumps({"missing_failure_types": [], "missing_model_scales": []}), encoding="utf-8")
            benchmark.write_text(
                json.dumps(
                    {
                        "detection_rate_after": 0.91,
                        "false_positive_rate_after": 0.02,
                        "regression_rate_after": 0.08,
                        "distribution_drift_score": 0.12,
                    }
                ),
                encoding="utf-8",
            )
            ladder.write_text(json.dumps({"large_ready": True}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_policy_patch_advisor",
                    "--failure-taxonomy-coverage",
                    str(taxonomy),
                    "--failure-distribution-benchmark",
                    str(benchmark),
                    "--model-scale-ladder",
                    str(ladder),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice") or {}
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(advice.get("suggested_action"), "keep")


if __name__ == "__main__":
    unittest.main()
