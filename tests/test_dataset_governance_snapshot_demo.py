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
            self.assertIn(
                payload.get("real_model_license_compliance_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("modelica_mutation_recipe_library_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("real_model_failure_yield_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("real_model_intake_backlog_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("modelica_moat_readiness_gate_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("real_model_supply_health_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("mutation_recipe_execution_audit_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("modelica_release_candidate_gate_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("intake_growth_advisor_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("intake_growth_advisor_history_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("intake_growth_advisor_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("intake_growth_execution_board_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("intake_growth_execution_board_execution_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("intake_growth_execution_board_history_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("intake_growth_execution_board_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("real_model_intake_portfolio_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("real_model_intake_portfolio_total_real_models"),
                (int, type(None)),
            )
            self.assertIn(
                payload.get("mutation_coverage_depth_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("mutation_coverage_depth_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("failure_distribution_stability_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("failure_distribution_stability_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("failure_distribution_stability_history_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("failure_distribution_stability_history_avg_stability_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("failure_distribution_stability_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("moat_anchor_brief_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("moat_anchor_brief_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("moat_anchor_brief_history_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("moat_anchor_brief_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("real_model_supply_pipeline_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("real_model_supply_pipeline_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("mutation_coverage_matrix_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("mutation_coverage_matrix_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("model_intake_board_history_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("model_intake_board_history_avg_board_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("model_intake_board_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("anchor_model_pack_history_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("anchor_model_pack_history_avg_pack_quality_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("anchor_model_pack_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIn(
                payload.get("failure_matrix_expansion_history_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )
            self.assertIsInstance(
                payload.get("failure_matrix_expansion_history_avg_expansion_readiness_score"),
                (int, float, type(None)),
            )
            self.assertIn(
                payload.get("failure_matrix_expansion_history_trend_status"),
                {"PASS", "NEEDS_REVIEW", "FAIL", None},
            )


if __name__ == "__main__":
    unittest.main()
