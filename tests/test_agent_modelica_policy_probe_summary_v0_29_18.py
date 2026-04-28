from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_policy_probe_summary_v0_29_18 import build_policy_probe_summary


def _write_result(path: Path) -> None:
    path.mkdir(parents=True)
    row = {
        "case_id": "sem_06",
        "final_verdict": "FAILED",
        "submitted": False,
        "token_used": 1000,
        "steps": [
            {"step": 1, "tool_calls": [{"name": "replaceable_partial_policy_check"}], "text": ""},
            {"step": 2, "tool_calls": [{"name": "check_model"}], "text": "The risk but this is the correct approach."},
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class PolicyProbeSummaryV02918Tests(unittest.TestCase):
    def test_build_summary_reports_policy_seen_without_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_result(run_dir)
            summary = build_policy_probe_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "policy_signal_seen_but_no_repair_gain")
            self.assertEqual(summary["policy_called_count"], 1)
            self.assertEqual(summary["policy_warning_overridden_count"], 1)
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
