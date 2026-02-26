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


if __name__ == "__main__":
    unittest.main()
