import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceSnapshotDemoTests(unittest.TestCase):
    def test_demo_dataset_governance_snapshot_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_governance_snapshot.sh"
        with tempfile.TemporaryDirectory() as d:
            try:
                proc = subprocess.run(
                    ["bash", str(script)],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"},
                    timeout=120,
                )
            except subprocess.TimeoutExpired as exc:
                self.fail(f"demo timed out after {exc.timeout}s")
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(
                (repo_root / "artifacts" / "dataset_governance_snapshot_demo" / "demo_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(
                payload.get("promotion_effectiveness_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(payload.get("failure_taxonomy_coverage_status"), {"PASS", "NEEDS_REVIEW", "FAIL", None})
            self.assertIn(
                payload.get("failure_distribution_benchmark_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(payload.get("model_scale_ladder_status"), {"PASS", "NEEDS_REVIEW", "FAIL", None})
            self.assertIn(
                payload.get("failure_policy_patch_advisor_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("modelica_library_provenance_guard_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("large_model_benchmark_pack_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("mutation_campaign_tracker_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("moat_public_scoreboard_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )


if __name__ == "__main__":
    unittest.main()
