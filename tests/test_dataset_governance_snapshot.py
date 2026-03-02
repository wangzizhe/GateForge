import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceSnapshotTests(unittest.TestCase):
    def test_snapshot_needs_review_on_governance_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pipeline = root / "pipeline.json"
            history = root / "history.json"
            history_trend = root / "history_trend.json"
            governance = root / "governance.json"
            governance_trend = root / "governance_trend.json"
            effectiveness = root / "effectiveness.json"
            strategy = root / "strategy.json"
            out = root / "snapshot.json"
            pipeline.write_text(json.dumps({"bundle_status": "PASS", "build_deduplicated_cases": 12}), encoding="utf-8")
            history.write_text(json.dumps({"total_records": 2, "latest_failure_case_rate": 0.3}), encoding="utf-8")
            history_trend.write_text(json.dumps({"status": "PASS", "trend": {"alerts": []}}), encoding="utf-8")
            governance.write_text(json.dumps({"latest_status": "PASS", "total_records": 2}), encoding="utf-8")
            governance_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["dataset_governance_fail_rate_increasing"]}}),
                encoding="utf-8",
            )
            effectiveness.write_text(json.dumps({"decision": "KEEP"}), encoding="utf-8")
            strategy.write_text(json.dumps({"advice": {"suggested_policy_profile": "dataset_default"}}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-pipeline-summary",
                    str(pipeline),
                    "--dataset-history-summary",
                    str(history),
                    "--dataset-history-trend",
                    str(history_trend),
                    "--dataset-governance-summary",
                    str(governance),
                    "--dataset-governance-trend",
                    str(governance_trend),
                    "--dataset-policy-effectiveness",
                    str(effectiveness),
                    "--dataset-strategy-advisor",
                    str(strategy),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_governance_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_strategy_apply_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            apply_history = root / "apply_history.json"
            apply_trend = root / "apply_trend.json"
            out = root / "snapshot.json"
            apply_history.write_text(
                json.dumps({"latest_final_status": "PASS", "fail_rate": 0.0, "needs_review_rate": 0.2}),
                encoding="utf-8",
            )
            apply_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["apply_fail_rate_increasing"]}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-strategy-apply-history",
                    str(apply_history),
                    "--dataset-strategy-apply-history-trend",
                    str(apply_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_strategy_apply_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_promotion_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            promotion_history = root / "promotion_history.json"
            promotion_trend = root / "promotion_trend.json"
            out = root / "snapshot.json"
            promotion_history.write_text(
                json.dumps({"latest_decision": "HOLD", "hold_rate": 0.5, "block_rate": 0.1}),
                encoding="utf-8",
            )
            promotion_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["promote_rate_decreasing"]}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-promotion-history",
                    str(promotion_history),
                    "--dataset-promotion-history-trend",
                    str(promotion_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_promotion_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_promotion_apply_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            promotion_apply_history = root / "promotion_apply_history.json"
            promotion_apply_trend = root / "promotion_apply_trend.json"
            out = root / "snapshot.json"
            promotion_apply_history.write_text(
                json.dumps({"latest_final_status": "PASS", "fail_rate": 0.0, "needs_review_rate": 0.3}),
                encoding="utf-8",
            )
            promotion_apply_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["apply_fail_rate_increasing"]}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-promotion-apply-history",
                    str(promotion_apply_history),
                    "--dataset-promotion-apply-history-trend",
                    str(promotion_apply_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_promotion_apply_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_promotion_effectiveness(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            promotion_effectiveness = root / "promotion_effectiveness.json"
            out = root / "snapshot.json"
            promotion_effectiveness.write_text(json.dumps({"decision": "NEEDS_REVIEW"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-promotion-effectiveness",
                    str(promotion_effectiveness),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_promotion_effectiveness_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_promotion_effectiveness_history_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history = root / "promotion_effectiveness_history.json"
            trend = root / "promotion_effectiveness_history_trend.json"
            out = root / "snapshot.json"
            history.write_text(
                json.dumps({"latest_decision": "KEEP", "rollback_review_rate": 0.0}),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["keep_rate_decreasing"]}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-promotion-effectiveness-history",
                    str(history),
                    "--dataset-promotion-effectiveness-history-trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_promotion_effectiveness_history_trend_needs_review", payload.get("risks", []))

    def test_snapshot_fail_on_pipeline_or_effectiveness_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pipeline = root / "pipeline.json"
            effectiveness = root / "effectiveness.json"
            out = root / "snapshot.json"
            pipeline.write_text(json.dumps({"bundle_status": "FAIL"}), encoding="utf-8")
            effectiveness.write_text(json.dumps({"decision": "ROLLBACK_REVIEW"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-pipeline-summary",
                    str(pipeline),
                    "--dataset-policy-effectiveness",
                    str(effectiveness),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            self.assertIn("dataset_pipeline_bundle_fail", payload.get("risks", []))

    def test_snapshot_needs_review_on_failure_taxonomy_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            coverage = root / "failure_taxonomy_coverage.json"
            out = root / "snapshot.json"
            coverage.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "total_cases": 3,
                        "unique_failure_type_count": 2,
                        "missing_failure_types": ["solver_non_convergence"],
                        "missing_model_scales": ["large"],
                        "missing_stages": ["compile"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-failure-taxonomy-coverage",
                    str(coverage),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_failure_taxonomy_coverage_needs_review", payload.get("risks", []))
            self.assertEqual((payload.get("kpis") or {}).get("dataset_failure_taxonomy_missing_model_scales_count"), 1)

    def test_snapshot_needs_review_on_failure_distribution_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "failure_distribution_benchmark.json"
            out = root / "snapshot.json"
            benchmark.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "detection_rate_after": 0.68,
                        "false_positive_rate_after": 0.17,
                        "regression_rate_after": 0.24,
                        "distribution_drift_score": 0.41,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-failure-distribution-benchmark",
                    str(benchmark),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_failure_distribution_benchmark_needs_review", payload.get("risks", []))
            self.assertEqual((payload.get("kpis") or {}).get("dataset_failure_distribution_drift_score"), 0.41)

    def test_snapshot_needs_review_on_model_scale_ladder(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ladder = root / "model_scale_ladder.json"
            out = root / "snapshot.json"
            ladder.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "medium_ready": True,
                        "large_ready": False,
                        "scale_counts": {"small": 5, "medium": 2, "large": 0},
                        "ci_recommendation": {"main": ["small_smoke", "medium_smoke"], "optional": ["medium_full"]},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-model-scale-ladder",
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
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_model_scale_ladder_needs_review", payload.get("risks", []))
            self.assertEqual((payload.get("kpis") or {}).get("dataset_model_scale_large_cases"), 0)

    def test_snapshot_needs_review_on_failure_policy_patch_advisor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "failure_policy_patch_advisor.json"
            out = root / "snapshot.json"
            advisor.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "advice": {
                            "suggested_action": "tighten_thresholds_and_require_large_review",
                            "confidence": 0.87,
                            "reasons": ["regression_rate_high", "large_scale_not_ready"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-failure-policy-patch-advisor",
                    str(advisor),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_failure_policy_patch_advisor_needs_review", payload.get("risks", []))
            self.assertEqual(
                (payload.get("kpis") or {}).get("dataset_failure_policy_patch_suggested_action"),
                "tighten_thresholds_and_require_large_review",
            )

    def test_snapshot_needs_review_on_moat_public_scoreboard(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            scoreboard = root / "moat_public_scoreboard.json"
            out = root / "snapshot.json"
            scoreboard.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "moat_public_score": 66.0,
                        "verdict": "INSUFFICIENT_EVIDENCE",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-moat-public-scoreboard",
                    str(scoreboard),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_moat_public_scoreboard_needs_review", payload.get("risks", []))
            self.assertEqual((payload.get("kpis") or {}).get("dataset_moat_public_verdict"), "INSUFFICIENT_EVIDENCE")

    def test_snapshot_needs_review_on_real_model_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            license_summary = root / "license.json"
            recipe_summary = root / "recipe.json"
            yield_summary = root / "yield.json"
            backlog_summary = root / "backlog.json"
            moat_gate_summary = root / "moat_gate.json"
            supply_health_summary = root / "supply_health.json"
            recipe_audit_summary = root / "recipe_audit.json"
            release_candidate_summary = root / "release_candidate.json"
            out = root / "snapshot.json"
            license_summary.write_text(
                json.dumps({"status": "PASS", "unknown_license_ratio_pct": 0.0, "disallowed_license_count": 0}),
                encoding="utf-8",
            )
            recipe_summary.write_text(
                json.dumps({"status": "PASS", "total_recipes": 8, "high_priority_recipes": 1}),
                encoding="utf-8",
            )
            yield_summary.write_text(
                json.dumps({"status": "PASS", "yield_per_accepted_model": 1.9, "matrix_execution_ratio_pct": 86.0}),
                encoding="utf-8",
            )
            backlog_summary.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "backlog_item_count": 4, "p0_count": 1}),
                encoding="utf-8",
            )
            moat_gate_summary.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "moat_readiness_score": 74.0, "release_recommendation": "HOLD"}),
                encoding="utf-8",
            )
            supply_health_summary.write_text(
                json.dumps({"status": "PASS", "supply_health_score": 79.0, "supply_gap_count": 1}),
                encoding="utf-8",
            )
            recipe_audit_summary.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "execution_coverage_pct": 62.0, "missing_recipe_count": 4}),
                encoding="utf-8",
            )
            release_candidate_summary.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "release_candidate_score": 73.0, "candidate_decision": "HOLD"}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-real-model-license-compliance",
                    str(license_summary),
                    "--dataset-modelica-mutation-recipe-library",
                    str(recipe_summary),
                    "--dataset-real-model-failure-yield",
                    str(yield_summary),
                    "--dataset-real-model-intake-backlog",
                    str(backlog_summary),
                    "--dataset-modelica-moat-readiness-gate",
                    str(moat_gate_summary),
                    "--dataset-real-model-supply-health",
                    str(supply_health_summary),
                    "--dataset-mutation-recipe-execution-audit",
                    str(recipe_audit_summary),
                    "--dataset-modelica-release-candidate-gate",
                    str(release_candidate_summary),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_real_model_intake_backlog_needs_review", payload.get("risks", []))
            self.assertIn("dataset_modelica_moat_readiness_gate_needs_review", payload.get("risks", []))
            self.assertIn("dataset_mutation_recipe_execution_audit_needs_review", payload.get("risks", []))
            self.assertIn("dataset_modelica_release_candidate_gate_needs_review", payload.get("risks", []))
            self.assertEqual((payload.get("kpis") or {}).get("dataset_modelica_mutation_recipe_total"), 8)
            self.assertEqual((payload.get("kpis") or {}).get("dataset_real_model_failure_yield_per_accepted_model"), 1.9)

    def test_snapshot_needs_review_on_intake_growth_advisor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            out = root / "snapshot.json"
            advisor.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "advice": {
                            "suggested_action": "execute_growth_recovery_plan",
                            "backlog_actions": [{"action_id": "add_candidates_large"}],
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-intake-growth-advisor",
                    str(advisor),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_intake_growth_advisor_needs_review", payload.get("risks", []))
            self.assertEqual(
                (payload.get("kpis") or {}).get("dataset_intake_growth_suggested_action"),
                "execute_growth_recovery_plan",
            )

    def test_snapshot_needs_review_on_intake_growth_advisor_history_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "snapshot.json"
            history.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "latest_suggested_action": "execute_targeted_growth_patch",
                        "recovery_plan_rate": 0.2,
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "trend": {"alerts": ["recovery_plan_rate_increasing"]},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-intake-growth-advisor-history",
                    str(history),
                    "--dataset-intake-growth-advisor-history-trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_intake_growth_advisor_history_needs_review", payload.get("risks", []))
            self.assertIn("dataset_intake_growth_advisor_history_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_intake_growth_execution_board_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            board = root / "board.json"
            board_history = root / "board_history.json"
            board_history_trend = root / "board_history_trend.json"
            out = root / "snapshot.json"
            board.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "execution_score": 71.0,
                        "critical_open_tasks": 1,
                        "projected_weeks_to_target": 2,
                    }
                ),
                encoding="utf-8",
            )
            board_history.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "avg_execution_score": 74.0,
                        "critical_open_tasks_rate": 0.5,
                    }
                ),
                encoding="utf-8",
            )
            board_history_trend.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "trend": {"alerts": ["critical_open_tasks_rate_increasing"]},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-intake-growth-execution-board",
                    str(board),
                    "--dataset-intake-growth-execution-board-history",
                    str(board_history),
                    "--dataset-intake-growth-execution-board-history-trend",
                    str(board_history_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_intake_growth_execution_board_needs_review", payload.get("risks", []))
            self.assertIn("dataset_intake_growth_execution_board_history_needs_review", payload.get("risks", []))
            self.assertIn(
                "dataset_intake_growth_execution_board_history_trend_needs_review",
                payload.get("risks", []),
            )

    def test_snapshot_needs_review_on_intake_portfolio_and_mutation_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            portfolio = root / "portfolio.json"
            coverage = root / "coverage.json"
            out = root / "snapshot.json"
            portfolio.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "total_real_models": 2,
                        "large_models": 0,
                        "license_clean_ratio_pct": 90.0,
                        "active_domains_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            coverage.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "coverage_depth_score": 72.0,
                        "uncovered_cells_count": 3,
                        "high_risk_gaps_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-real-model-intake-portfolio",
                    str(portfolio),
                    "--dataset-mutation-coverage-depth",
                    str(coverage),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_real_model_intake_portfolio_needs_review", payload.get("risks", []))
            self.assertIn("dataset_mutation_coverage_depth_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_failure_distribution_stability(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stability = root / "stability.json"
            out = root / "snapshot.json"
            stability.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "stability_score": 68.0,
                        "drift_band": "medium",
                        "rare_failure_replay_rate": 0.25,
                        "delta_distribution_drift_score": 0.12,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-failure-distribution-stability",
                    str(stability),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_failure_distribution_stability_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_moat_anchor_brief_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "snapshot.json"
            anchor.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "anchor_brief_score": 68.0, "recommendation": "PUBLISH_WITH_GUARDS"}),
                encoding="utf-8",
            )
            history.write_text(
                json.dumps({"status": "PASS", "total_records": 4, "publish_rate": 0.75, "latest_recommendation": "PUBLISH"}),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS"}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-moat-anchor-brief",
                    str(anchor),
                    "--dataset-moat-anchor-brief-history",
                    str(history),
                    "--dataset-moat-anchor-brief-history-trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_moat_anchor_brief_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_supply_pipeline_and_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            supply = root / "supply.json"
            matrix = root / "matrix.json"
            out = root / "snapshot.json"
            supply.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "supply_pipeline_score": 61.0, "new_models_30d": 0}),
                encoding="utf-8",
            )
            matrix.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "matrix_coverage_score": 70.0, "high_risk_uncovered_cells": 3}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-real-model-supply-pipeline",
                    str(supply),
                    "--dataset-mutation-coverage-matrix",
                    str(matrix),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_real_model_supply_pipeline_needs_review", payload.get("risks", []))
            self.assertIn("dataset_mutation_coverage_matrix_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_stability_history_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "snapshot.json"
            history.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "total_records": 4, "avg_stability_score": 72.0}),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"status_transition": "PASS->NEEDS_REVIEW"}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-failure-distribution-stability-history",
                    str(history),
                    "--dataset-failure-distribution-stability-history-trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_failure_distribution_stability_history_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_model_asset_history_chains(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake_history = root / "intake_history.json"
            intake_history_trend = root / "intake_history_trend.json"
            anchor_history = root / "anchor_history.json"
            anchor_history_trend = root / "anchor_history_trend.json"
            expansion_history = root / "expansion_history.json"
            expansion_history_trend = root / "expansion_history_trend.json"
            out = root / "snapshot.json"
            intake_history.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "total_records": 4, "avg_board_score": 72.0}),
                encoding="utf-8",
            )
            intake_history_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"status_transition": "PASS->NEEDS_REVIEW"}}),
                encoding="utf-8",
            )
            anchor_history.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "total_records": 4, "avg_pack_quality_score": 77.0}),
                encoding="utf-8",
            )
            anchor_history_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"status_transition": "PASS->NEEDS_REVIEW"}}),
                encoding="utf-8",
            )
            expansion_history.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "total_records": 4, "avg_expansion_readiness_score": 70.0}),
                encoding="utf-8",
            )
            expansion_history_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"status_transition": "PASS->NEEDS_REVIEW"}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-model-intake-board-history",
                    str(intake_history),
                    "--dataset-model-intake-board-history-trend",
                    str(intake_history_trend),
                    "--dataset-anchor-model-pack-history",
                    str(anchor_history),
                    "--dataset-anchor-model-pack-history-trend",
                    str(anchor_history_trend),
                    "--dataset-failure-matrix-expansion-history",
                    str(expansion_history),
                    "--dataset-failure-matrix-expansion-history-trend",
                    str(expansion_history_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_model_intake_board_history_needs_review", payload.get("risks", []))
            self.assertIn("dataset_model_intake_board_history_trend_needs_review", payload.get("risks", []))
            self.assertIn("dataset_anchor_model_pack_history_needs_review", payload.get("risks", []))
            self.assertIn("dataset_anchor_model_pack_history_trend_needs_review", payload.get("risks", []))
            self.assertIn("dataset_failure_matrix_expansion_history_needs_review", payload.get("risks", []))
            self.assertIn("dataset_failure_matrix_expansion_history_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_model_asset_momentum_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            momentum = root / "momentum.json"
            momentum_history = root / "momentum_history.json"
            momentum_history_trend = root / "momentum_history_trend.json"
            out = root / "snapshot.json"
            momentum.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "momentum_score": 68.0, "delta_total_real_models": 0}),
                encoding="utf-8",
            )
            momentum_history.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "total_records": 4, "avg_momentum_score": 70.0}),
                encoding="utf-8",
            )
            momentum_history_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"status_transition": "PASS->NEEDS_REVIEW"}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-model-asset-momentum",
                    str(momentum),
                    "--dataset-model-asset-momentum-history",
                    str(momentum_history),
                    "--dataset-model-asset-momentum-history-trend",
                    str(momentum_history_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_model_asset_momentum_needs_review", payload.get("risks", []))
            self.assertIn("dataset_model_asset_momentum_history_needs_review", payload.get("risks", []))
            self.assertIn("dataset_model_asset_momentum_history_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_model_asset_target_gap(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target_gap = root / "target_gap.json"
            out = root / "snapshot.json"
            target_gap.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "target_gap_score": 28.5, "critical_gap_count": 1}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-model-asset-target-gap",
                    str(target_gap),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_model_asset_target_gap_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_model_asset_target_gap_history_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target_gap_history = root / "target_gap_history.json"
            target_gap_history_trend = root / "target_gap_history_trend.json"
            out = root / "snapshot.json"
            target_gap_history.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "total_records": 4, "avg_target_gap_score": 24.5}),
                encoding="utf-8",
            )
            target_gap_history_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"status_transition": "PASS->NEEDS_REVIEW"}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-model-asset-target-gap-history",
                    str(target_gap_history),
                    "--dataset-model-asset-target-gap-history-trend",
                    str(target_gap_history_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_model_asset_target_gap_history_needs_review", payload.get("risks", []))
            self.assertIn("dataset_model_asset_target_gap_history_trend_needs_review", payload.get("risks", []))

    def test_snapshot_needs_review_on_moat_weekly_summary_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            weekly = root / "weekly.json"
            weekly_history = root / "weekly_history.json"
            weekly_trend = root / "weekly_trend.json"
            out = root / "snapshot.json"
            weekly.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "week_tag": "2026-W10",
                        "kpis": {
                            "real_model_count": 8,
                            "reproducible_mutation_count": 24,
                            "failure_distribution_stability_score": 78.0,
                            "gateforge_vs_plain_ci_advantage_score": 6,
                        },
                    }
                ),
                encoding="utf-8",
            )
            weekly_history.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "total_records": 2,
                        "latest_week_tag": "2026-W10",
                        "avg_stability_score": 84.0,
                        "avg_advantage_score": 7.0,
                    }
                ),
                encoding="utf-8",
            )
            weekly_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"status_transition": "PASS->NEEDS_REVIEW"}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot",
                    "--dataset-moat-weekly-summary",
                    str(weekly),
                    "--dataset-moat-weekly-summary-history",
                    str(weekly_history),
                    "--dataset-moat-weekly-summary-history-trend",
                    str(weekly_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("dataset_moat_weekly_summary_needs_review", payload.get("risks", []))
            self.assertIn("dataset_moat_weekly_summary_history_trend_needs_review", payload.get("risks", []))
            self.assertEqual((payload.get("kpis") or {}).get("dataset_moat_weekly_summary_week_tag"), "2026-W10")


if __name__ == "__main__":
    unittest.main()
