from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_critique_salience_summary_v0_30_1 import (
    build_candidate_critique_salience_summary,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


def _write(path: Path, *, critique_count: int) -> None:
    path.mkdir(parents=True)
    calls = [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}]
    calls.extend({"name": "candidate_acceptance_critique", "arguments": {"omc_passed": True}} for _ in range(critique_count))
    row = {
        "case_id": "sem_case",
        "final_verdict": "FAILED",
        "submitted": False,
        "token_used": 1000,
        "steps": [{"step": 1, "tool_calls": calls, "tool_results": []}],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class CandidateCritiqueSalienceSummaryV0301Tests(unittest.TestCase):
    def test_summary_reports_salience_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            probe = root / "probe"
            _write(baseline, critique_count=0)
            _write(probe, critique_count=1)
            summary = build_candidate_critique_salience_summary(
                baseline_dir=baseline,
                probe_dir=probe,
                out_dir=root / "out",
            )
            self.assertEqual(summary["decision"], "candidate_critique_invoked_without_capability_gain")
            self.assertEqual(summary["probe_critique_tool_count"], 1)

    def test_required_profile_is_exposed(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy_candidate_critique_required")}
        self.assertIn("candidate_acceptance_critique", names)
        self.assertIn("strict discoverability", get_tool_profile_guidance("replaceable_policy_candidate_critique_required"))


if __name__ == "__main__":
    unittest.main()
