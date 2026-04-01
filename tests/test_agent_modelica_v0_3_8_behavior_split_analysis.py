from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_8_behavior_split_analysis import build_v0_3_8_behavior_split_analysis


class AgentModelicaV038BehaviorSplitAnalysisTests(unittest.TestCase):
    def test_reports_partial_forcing_on_mixed_live_split(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 10,
                            "successful_case_count": 10,
                            "success_after_branch_switch_count": 5,
                            "success_without_branch_switch_evidence_count": 5,
                            "branch_switch_evidenced_success_pct": 50.0,
                            "success_without_branch_switch_evidence_pct": 50.0,
                        },
                        "tasks": [
                            {"task_id": "a", "success_after_branch_switch": True, "success_without_branch_switch_evidence": False},
                            {"task_id": "b", "success_after_branch_switch": True, "success_without_branch_switch_evidence": False},
                            {"task_id": "c", "success_after_branch_switch": True, "success_without_branch_switch_evidence": False},
                            {"task_id": "d", "success_after_branch_switch": False, "success_without_branch_switch_evidence": True},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_8_behavior_split_analysis(
                refreshed_summary_path=str(refreshed),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PARTIAL_FORCING")
            self.assertEqual(payload["recommendation"], "explicit_branch_switch_subfamily_selection")


if __name__ == "__main__":
    unittest.main()
