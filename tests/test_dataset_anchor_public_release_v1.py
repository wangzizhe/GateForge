import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetAnchorPublicReleaseV1Tests(unittest.TestCase):
    def test_public_release_pass_when_signals_are_strong(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            compare = root / "compare.json"
            benchmark = root / "benchmark.json"
            moat = root / "moat.json"
            push = root / "push.json"
            out = root / "summary.json"

            anchor.write_text(
                json.dumps(
                    {
                        "release_score": 90.0,
                        "release_bundle_id": "anchor_release_v3_20260226",
                        "reproducible_playbook": ["bash scripts/demo_a.sh", "bash scripts/demo_b.sh"],
                    }
                ),
                encoding="utf-8",
            )
            compare.write_text(json.dumps({"verdict": "GATEFORGE_ADVANTAGE", "advantage_score": 8}), encoding="utf-8")
            benchmark.write_text(
                json.dumps({"validated_match_ratio_pct": 92.0, "failure_type_drift": 0.12}),
                encoding="utf-8",
            )
            moat.write_text(json.dumps({"metrics": {"moat_score": 83.0}}), encoding="utf-8")
            push.write_text(json.dumps({"status": "PASS", "push_target_large_cases": 0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_public_release_v1",
                    "--anchor-release-bundle-v3-summary",
                    str(anchor),
                    "--gateforge-vs-plain-ci-summary",
                    str(compare),
                    "--failure-distribution-benchmark-v2-summary",
                    str(benchmark),
                    "--moat-trend-snapshot-summary",
                    str(moat),
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
            self.assertEqual(summary.get("public_release_ready"), True)
            self.assertGreaterEqual(float(summary.get("public_release_score", 0.0)), 75.0)

    def test_public_release_needs_review_when_risk_disclosures_exist(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            compare = root / "compare.json"
            benchmark = root / "benchmark.json"
            push = root / "push.json"
            out = root / "summary.json"

            anchor.write_text(json.dumps({"release_score": 78.0, "release_bundle_id": "anchor_release_v3_20260226"}), encoding="utf-8")
            compare.write_text(json.dumps({"verdict": "INCONCLUSIVE", "advantage_score": -1}), encoding="utf-8")
            benchmark.write_text(json.dumps({"validated_match_ratio_pct": 65.0, "failure_type_drift": 0.44}), encoding="utf-8")
            push.write_text(json.dumps({"status": "NEEDS_REVIEW", "push_target_large_cases": 4}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_public_release_v1",
                    "--anchor-release-bundle-v3-summary",
                    str(anchor),
                    "--gateforge-vs-plain-ci-summary",
                    str(compare),
                    "--failure-distribution-benchmark-v2-summary",
                    str(benchmark),
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
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            risks = summary.get("risk_disclosures") if isinstance(summary.get("risk_disclosures"), list) else []
            self.assertIn("comparison_verdict_not_gateforge_advantage", risks)
            self.assertIn("large_model_coverage_gap_open", risks)

    def test_public_release_fail_when_required_sources_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_public_release_v1",
                    "--anchor-release-bundle-v3-summary",
                    str(root / "missing_anchor.json"),
                    "--gateforge-vs-plain-ci-summary",
                    str(root / "missing_compare.json"),
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
