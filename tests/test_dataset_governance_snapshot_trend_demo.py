import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceSnapshotTrendDemoTests(unittest.TestCase):
    def test_demo_dataset_governance_snapshot_trend_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_governance_snapshot_trend.sh"
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
                (repo_root / "artifacts" / "dataset_governance_snapshot_trend_demo" / "demo_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIn("->", str(payload.get("status_transition")))
            self.assertIn("->", str(payload.get("promotion_effectiveness_history_trend_transition")))
            self.assertIn("->", str(payload.get("failure_taxonomy_coverage_status_transition")))
            self.assertIn("->", str(payload.get("failure_distribution_benchmark_status_transition")))
            self.assertIn("->", str(payload.get("model_scale_ladder_status_transition")))
            self.assertIn("->", str(payload.get("failure_policy_patch_advisor_status_transition")))
            self.assertIn("->", str(payload.get("modelica_library_provenance_guard_status_transition")))
            self.assertIn("->", str(payload.get("large_model_benchmark_pack_status_transition")))
            self.assertIn("->", str(payload.get("mutation_campaign_tracker_status_transition")))
            self.assertIn("->", str(payload.get("moat_public_scoreboard_status_transition")))
            self.assertIn("->", str(payload.get("real_model_license_compliance_status_transition")))
            self.assertIn("->", str(payload.get("modelica_mutation_recipe_library_status_transition")))
            self.assertIn("->", str(payload.get("real_model_failure_yield_status_transition")))
            self.assertIn("->", str(payload.get("real_model_intake_backlog_status_transition")))
            self.assertIn("->", str(payload.get("modelica_moat_readiness_gate_status_transition")))
            self.assertIn("->", str(payload.get("real_model_supply_health_status_transition")))
            self.assertIn("->", str(payload.get("mutation_recipe_execution_audit_status_transition")))
            self.assertIn("->", str(payload.get("modelica_release_candidate_gate_status_transition")))
            self.assertIn("->", str(payload.get("intake_growth_advisor_status_transition")))
            self.assertIn("->", str(payload.get("intake_growth_advisor_history_status_transition")))
            self.assertIn("->", str(payload.get("intake_growth_advisor_history_trend_status_transition")))
            self.assertIsInstance(payload.get("status_delta_alert_count"), int)
            self.assertIsInstance(payload.get("severity_score"), int)
            self.assertIn(payload.get("severity_level"), {"low", "medium", "high"})


if __name__ == "__main__":
    unittest.main()
