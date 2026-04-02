from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_12_closeout import build_v0_3_12_closeout


class AgentModelicaV0312CloseoutTests(unittest.TestCase):
    def test_build_closeout_records_inconclusive_block_b_and_paper_route_note(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runner = root / "runner.json"
            decision = root / "decision.json"
            audit = root / "audit.json"
            failure = root / "failure.json"
            runner.write_text(json.dumps({"planner_backend": "gemini", "task_count": 8}), encoding="utf-8")
            decision.write_text(
                json.dumps(
                    {
                        "decision": "inconclusive_insufficient_labeled_cases",
                        "reason": "successful_labeled_count_below_minimum",
                        "metrics": {
                            "admitted_count": 8,
                            "successful_case_count": 0,
                            "successful_labeled_count": 0,
                            "unknown_success_pct": 0.0,
                            "true_continuity_pct": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            audit.write_text(
                json.dumps(
                    {
                        "overall": {
                            "paper_claim_status": "planner_value_visible_only_on_calibration_lane",
                            "paper_claim_recommendation": "treat_harder_holdout_as_failure_sidecar_and_design_new_track_c_slice",
                            "deterministic_dominated_lanes": ["track_a", "track_b"],
                            "planner_expressive_lanes": ["planner_sensitive"],
                            "unresolved_lanes": ["harder_holdout"],
                        }
                    }
                ),
                encoding="utf-8",
            )
            failure.write_text(json.dumps({"representative_case_count": 1, "representative_cases": [{"mutation_id": "demo"}]}), encoding="utf-8")

            payload = build_v0_3_12_closeout(
                block_b_runner_summary_path=str(runner),
                block_b_decision_summary_path=str(decision),
                resolution_audit_summary_path=str(audit),
                failure_note_summary_path=str(failure),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["classification"], "inconclusive_insufficient_labeled_cases")
            self.assertEqual(payload["version_status"], "hypothesis_not_resolved")
            self.assertEqual(
                payload["paper_claim_recommendation"],
                "treat_harder_holdout_as_failure_sidecar_and_design_new_track_c_slice",
            )
            self.assertEqual(payload["evidence"]["failure_note"]["representative_case_count"], 1)


if __name__ == "__main__":
    unittest.main()
