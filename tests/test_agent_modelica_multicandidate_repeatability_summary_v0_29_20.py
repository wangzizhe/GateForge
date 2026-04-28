from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_multicandidate_repeatability_summary_v0_29_20 import (
    build_multicandidate_repeatability_summary,
)


def _write_run(path: Path, verdict: str) -> None:
    path.mkdir(parents=True)
    row = {
        "case_id": "sem_07",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [
            {"tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X equation x=1; end X;"}}]},
            {"tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X equation x=2; end X;"}}]},
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class MulticandidateRepeatabilitySummaryV02920Tests(unittest.TestCase):
    def test_build_summary_reports_non_repeatable_positive_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            run_2 = root / "run_2"
            _write_run(run_1, "PASS")
            _write_run(run_2, "FAILED")
            summary = build_multicandidate_repeatability_summary(
                run_dirs=[run_1, run_2],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "multicandidate_positive_signal_not_repeatable")
            self.assertEqual(summary["positive_run_count"], 1)
            self.assertFalse(summary["cases"][0]["stable_pass"])
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
