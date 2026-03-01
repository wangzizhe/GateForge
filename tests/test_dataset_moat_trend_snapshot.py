import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatTrendSnapshotTests(unittest.TestCase):
    def test_snapshot_pass_when_moat_score_high(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            evidence = root / "evidence.json"
            registry = root / "registry.json"
            backlog = root / "backlog.json"
            replay = root / "replay.json"
            checkpoint = root / "checkpoint.json"
            checkpoint_trend = root / "checkpoint_trend.json"
            brief = root / "brief.json"
            intake = root / "intake.json"
            previous_intake = root / "previous_intake.json"
            execution_board = root / "execution_board.json"
            execution_board_history = root / "execution_board_history.json"
            execution_board_history_trend = root / "execution_board_history_trend.json"
            model_intake_board_history = root / "model_intake_board_history.json"
            model_intake_board_history_trend = root / "model_intake_board_history_trend.json"
            anchor_model_pack_history = root / "anchor_model_pack_history.json"
            anchor_model_pack_history_trend = root / "anchor_model_pack_history_trend.json"
            failure_matrix_expansion_history = root / "failure_matrix_expansion_history.json"
            failure_matrix_expansion_history_trend = root / "failure_matrix_expansion_history_trend.json"
            previous = root / "previous.json"
            out = root / "summary.json"

            evidence.write_text(json.dumps({"status": "PASS", "evidence_strength_score": 80, "evidence_sections_present": 8}), encoding="utf-8")
            registry.write_text(json.dumps({"total_records": 30, "missing_model_scales": []}), encoding="utf-8")
            backlog.write_text(json.dumps({"total_open_tasks": 3, "priority_counts": {"P0": 0}}), encoding="utf-8")
            replay.write_text(json.dumps({"status": "PASS", "recommendation": "ADOPT_PATCH", "evaluation_score": 5}), encoding="utf-8")
            checkpoint.write_text(json.dumps({"status": "PASS", "checkpoint_score": 84.0, "milestone_decision": "GO"}), encoding="utf-8")
            checkpoint_trend.write_text(json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS"}}), encoding="utf-8")
            brief.write_text(json.dumps({"milestone_status": "PASS", "milestone_decision": "GO"}), encoding="utf-8")
            intake.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "accepted_count": 4,
                        "accepted_large_count": 1,
                        "reject_rate_pct": 22.5,
                        "weekly_target_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            previous_intake.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "accepted_count": 3,
                        "accepted_large_count": 0,
                        "reject_rate_pct": 30.0,
                        "weekly_target_status": "NEEDS_REVIEW",
                    }
                ),
                encoding="utf-8",
            )
            execution_board.write_text(
                json.dumps({"status": "PASS", "execution_score": 84.0, "critical_open_tasks": 0, "projected_weeks_to_target": 0}),
                encoding="utf-8",
            )
            execution_board_history.write_text(
                json.dumps({"status": "PASS", "avg_execution_score": 82.0, "critical_open_tasks_rate": 0.0}),
                encoding="utf-8",
            )
            execution_board_history_trend.write_text(
                json.dumps({"status": "PASS", "trend": {"alerts": []}}),
                encoding="utf-8",
            )
            model_intake_board_history.write_text(
                json.dumps({"status": "PASS", "avg_board_score": 81.0, "blocked_rate": 0.15, "ready_rate": 0.5, "ingested_rate": 0.35}),
                encoding="utf-8",
            )
            model_intake_board_history_trend.write_text(
                json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS", "alerts": []}}),
                encoding="utf-8",
            )
            anchor_model_pack_history.write_text(
                json.dumps({"status": "PASS", "avg_pack_quality_score": 84.0, "avg_selected_cases": 24.0, "avg_selected_large_cases": 7.0, "avg_unique_failure_types": 5.0}),
                encoding="utf-8",
            )
            anchor_model_pack_history_trend.write_text(
                json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS", "alerts": []}}),
                encoding="utf-8",
            )
            failure_matrix_expansion_history.write_text(
                json.dumps({"status": "PASS", "avg_expansion_readiness_score": 78.0, "avg_high_risk_uncovered_cells": 0.0, "avg_planned_expansion_tasks": 7.0}),
                encoding="utf-8",
            )
            failure_matrix_expansion_history_trend.write_text(
                json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS", "alerts": []}}),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "metrics": {
                            "milestone_readiness_index": 70,
                            "moat_score": 60,
                        },
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_trend_snapshot",
                    "--evidence-pack",
                    str(evidence),
                    "--failure-corpus-registry-summary",
                    str(registry),
                    "--blind-spot-backlog",
                    str(backlog),
                    "--policy-patch-replay-evaluator",
                    str(replay),
                    "--milestone-checkpoint-summary",
                    str(checkpoint),
                    "--milestone-checkpoint-trend-summary",
                    str(checkpoint_trend),
                    "--milestone-public-brief-summary",
                    str(brief),
                    "--real-model-intake-summary",
                    str(intake),
                    "--previous-real-model-intake-summary",
                    str(previous_intake),
                    "--intake-growth-execution-board-summary",
                    str(execution_board),
                    "--intake-growth-execution-board-history-summary",
                    str(execution_board_history),
                    "--intake-growth-execution-board-history-trend-summary",
                    str(execution_board_history_trend),
                    "--model-intake-board-history-summary",
                    str(model_intake_board_history),
                    "--model-intake-board-history-trend-summary",
                    str(model_intake_board_history_trend),
                    "--anchor-model-pack-history-summary",
                    str(anchor_model_pack_history),
                    "--anchor-model-pack-history-trend-summary",
                    str(anchor_model_pack_history_trend),
                    "--failure-matrix-expansion-history-summary",
                    str(failure_matrix_expansion_history),
                    "--failure-matrix-expansion-history-trend-summary",
                    str(failure_matrix_expansion_history_trend),
                    "--previous-snapshot",
                    str(previous),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertGreaterEqual(float((payload.get("metrics") or {}).get("moat_score", 0.0)), 70.0)
            self.assertGreaterEqual(float((payload.get("metrics") or {}).get("milestone_readiness_index", 0.0)), 75.0)
            self.assertIn("intake_growth_score", payload.get("metrics", {}))
            self.assertIn("execution_readiness_index", payload.get("metrics", {}))
            self.assertIn("model_asset_quality_index", payload.get("metrics", {}))
            self.assertIn("expansion_execution_index", payload.get("metrics", {}))
            self.assertEqual(int((payload.get("intake_growth") or {}).get("accepted_count_delta", 0)), 1)
            self.assertEqual(int((payload.get("intake_growth") or {}).get("accepted_large_delta", 0)), 1)

    def test_snapshot_fail_when_evidence_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            evidence = root / "evidence.json"
            out = root / "summary.json"
            evidence.write_text(json.dumps({"status": "FAIL", "evidence_strength_score": 10, "evidence_sections_present": 1}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_trend_snapshot",
                    "--evidence-pack",
                    str(evidence),
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


if __name__ == "__main__":
    unittest.main()
