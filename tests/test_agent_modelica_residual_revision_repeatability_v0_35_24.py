from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_residual_revision_repeatability_v0_35_24 import (
    build_residual_revision_repeatability,
)
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


def _write_run(path: Path, verdict: str) -> None:
    path.mkdir()
    row = {
        "case_id": TARGET_CASE_ID,
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "steps": [{"step": 1, "tool_calls": [{"name": "residual_hypothesis_consistency_check"}]}],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ResidualRevisionRepeatabilityV03524Tests(unittest.TestCase):
    def test_positive_but_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run1 = root / "run1"
            run2 = root / "run2"
            _write_run(run1, "PASS")
            _write_run(run2, "FAILED")
            summary = build_residual_revision_repeatability(run_dirs=[run1, run2], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_counts"], [1, 0])
            self.assertEqual(summary["decision"], "residual_revision_positive_but_unstable")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_residual_revision_repeatability(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
