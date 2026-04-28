from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_replaceable_expansion_summary_v0_29_21 import build_replaceable_expansion_summary


def _write_results(path: Path) -> None:
    path.mkdir(parents=True)
    rows = [
        {
            "case_id": "sem_pass",
            "final_verdict": "PASS",
            "submitted": True,
            "token_used": 1000,
            "steps": [{"tool_calls": [{"name": "submit_final", "arguments": {"model_text": "model X end X;"}}]}],
        },
        {
            "case_id": "sem_fail",
            "final_verdict": "FAILED",
            "submitted": False,
            "token_used": 50000,
            "steps": [{"tool_calls": [{"name": "check_model", "arguments": {"model_text": "model Y end Y;"}}]}],
        },
    ]
    (path / "results.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class ReplaceableExpansionSummaryV02921Tests(unittest.TestCase):
    def test_build_summary_classifies_mixed_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_results(run_dir)
            summary = build_replaceable_expansion_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(summary["hard_negative_candidate_count"], 1)
            self.assertEqual(summary["decision"], "family_expansion_yields_mixed_anchor_and_hard_negative_samples")
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
