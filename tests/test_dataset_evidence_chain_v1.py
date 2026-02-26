import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetEvidenceChainV1Tests(unittest.TestCase):
    def test_chain_pass_when_required_steps_are_strong(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            store = root / "store.json"
            calibrator = root / "calibrator.json"
            validator = root / "validator.json"
            benchmark = root / "benchmark.json"
            release = root / "release.json"
            push = root / "push.json"
            out = root / "summary.json"

            store.write_text(json.dumps({"status": "PASS", "ingested_records": 4}), encoding="utf-8")
            calibrator.write_text(json.dumps({"status": "PASS", "expected_match_ratio_pct": 92.0}), encoding="utf-8")
            validator.write_text(json.dumps({"status": "PASS", "expected_match_ratio_pct": 90.0}), encoding="utf-8")
            benchmark.write_text(json.dumps({"status": "PASS", "failure_type_drift": 0.14}), encoding="utf-8")
            release.write_text(json.dumps({"status": "PASS", "public_release_score": 86.0}), encoding="utf-8")
            push.write_text(json.dumps({"status": "PASS", "push_target_large_cases": 0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_evidence_chain_v1",
                    "--replay-observation-store-summary",
                    str(store),
                    "--failure-label-calibrator-summary",
                    str(calibrator),
                    "--mutation-validator-summary",
                    str(validator),
                    "--failure-distribution-benchmark-v2-summary",
                    str(benchmark),
                    "--anchor-public-release-v1-summary",
                    str(release),
                    "--large-coverage-push-v1-summary",
                    str(push),
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
            self.assertGreaterEqual(float(summary.get("chain_health_score", 0.0)), 70.0)
            self.assertEqual(float(summary.get("chain_completeness_pct", 0.0)), 100.0)

    def test_chain_needs_review_when_drift_or_step_warning_exists(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            store = root / "store.json"
            calibrator = root / "calibrator.json"
            validator = root / "validator.json"
            benchmark = root / "benchmark.json"
            out = root / "summary.json"

            store.write_text(json.dumps({"status": "PASS", "ingested_records": 0}), encoding="utf-8")
            calibrator.write_text(json.dumps({"status": "NEEDS_REVIEW", "expected_match_ratio_pct": 75.0}), encoding="utf-8")
            validator.write_text(json.dumps({"status": "PASS", "expected_match_ratio_pct": 80.0}), encoding="utf-8")
            benchmark.write_text(json.dumps({"status": "PASS", "failure_type_drift": 0.41}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_evidence_chain_v1",
                    "--replay-observation-store-summary",
                    str(store),
                    "--failure-label-calibrator-summary",
                    str(calibrator),
                    "--mutation-validator-summary",
                    str(validator),
                    "--failure-distribution-benchmark-v2-summary",
                    str(benchmark),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertIn("failure_distribution_drift_high", summary.get("alerts", []))

    def test_chain_fails_when_required_source_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_evidence_chain_v1",
                    "--replay-observation-store-summary",
                    str(root / "missing_store.json"),
                    "--failure-label-calibrator-summary",
                    str(root / "missing_calibrator.json"),
                    "--mutation-validator-summary",
                    str(root / "missing_validator.json"),
                    "--failure-distribution-benchmark-v2-summary",
                    str(root / "missing_benchmark.json"),
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
