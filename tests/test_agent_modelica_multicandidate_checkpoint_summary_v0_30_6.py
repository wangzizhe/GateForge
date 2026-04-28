from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_multicandidate_checkpoint_summary_v0_30_6 import (
    build_multicandidate_checkpoint_summary,
)


def _write(path: Path, *, case_id: str, verdict: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [{"name": "check_model", "result": "Failed to build model"}],
            }
        ],
    }
    with (path / "results.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


class MulticandidateCheckpointSummaryV0306Tests(unittest.TestCase):
    def test_summary_reports_no_discovery_gain_for_one_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write(run_dir, case_id="sem_a", verdict="PASS")
            _write(run_dir, case_id="sem_b", verdict="FAILED")
            summary = build_multicandidate_checkpoint_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["version"], "v0.30.6")
            self.assertEqual(summary["decision"], "multicandidate_checkpoint_no_discovery_gain")


if __name__ == "__main__":
    unittest.main()
