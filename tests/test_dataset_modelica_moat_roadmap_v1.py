import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaMoatRoadmapV1Tests(unittest.TestCase):
    def test_roadmap_pass_when_all_inputs_are_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain = root / "chain.json"
            saturation = root / "saturation.json"
            push = root / "push.json"
            release = root / "release.json"
            out = root / "summary.json"

            chain.write_text(json.dumps({"status": "PASS", "chain_health_score": 84.0}), encoding="utf-8")
            saturation.write_text(json.dumps({"status": "PASS", "saturation_index": 86.0, "total_gap_actions": 0}), encoding="utf-8")
            push.write_text(json.dumps({"status": "PASS", "push_target_large_cases": 0}), encoding="utf-8")
            release.write_text(json.dumps({"status": "PASS", "public_release_score": 88.0, "public_release_ready": True}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_moat_roadmap_v1",
                    "--evidence-chain-summary",
                    str(chain),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--large-coverage-push-v1-summary",
                    str(push),
                    "--anchor-public-release-v1-summary",
                    str(release),
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
            self.assertGreaterEqual(float(summary.get("roadmap_health_score", 0.0)), 75.0)

    def test_roadmap_needs_review_with_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain = root / "chain.json"
            saturation = root / "saturation.json"
            push = root / "push.json"
            release = root / "release.json"
            out = root / "summary.json"

            chain.write_text(json.dumps({"status": "NEEDS_REVIEW", "chain_health_score": 62.0}), encoding="utf-8")
            saturation.write_text(json.dumps({"status": "NEEDS_REVIEW", "saturation_index": 54.0, "total_gap_actions": 5}), encoding="utf-8")
            push.write_text(json.dumps({"status": "NEEDS_REVIEW", "push_target_large_cases": 6}), encoding="utf-8")
            release.write_text(json.dumps({"status": "NEEDS_REVIEW", "public_release_score": 70.0, "public_release_ready": False}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_moat_roadmap_v1",
                    "--evidence-chain-summary",
                    str(chain),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--large-coverage-push-v1-summary",
                    str(push),
                    "--anchor-public-release-v1-summary",
                    str(release),
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
            self.assertIn("evidence_chain_not_pass", summary.get("alerts", []))

    def test_roadmap_fails_when_required_source_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_moat_roadmap_v1",
                    "--evidence-chain-summary",
                    str(root / "missing_chain.json"),
                    "--failure-corpus-saturation-summary",
                    str(root / "missing_sat.json"),
                    "--large-coverage-push-v1-summary",
                    str(root / "missing_push.json"),
                    "--anchor-public-release-v1-summary",
                    str(root / "missing_release.json"),
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
