from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_rerun_summary_v0_29_14 import build_semantic_rerun_summary


def _write_run(path: Path, verdict: str) -> None:
    path.mkdir(parents=True)
    row = {
        "case_id": "sem_03",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [{"tool_calls": [{"name": "check_model"}]}],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class SemanticRerunSummaryV02914Tests(unittest.TestCase):
    def test_build_summary_marks_unstable_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_01 = root / "run_01"
            run_02 = root / "run_02"
            _write_run(run_01, "PASS")
            _write_run(run_02, "FAILED")
            summary = build_semantic_rerun_summary(run_dirs=[run_01, run_02], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["unstable_case_count"], 1)
            self.assertEqual(summary["decision"], "semantic_narrow_not_stable_enough_for_promotion")
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
