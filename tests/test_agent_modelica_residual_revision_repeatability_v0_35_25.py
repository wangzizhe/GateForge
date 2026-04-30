from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_residual_revision_repeatability_v0_35_25 import (
    build_residual_revision_repeatability_v0_35_25,
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


class ResidualRevisionRepeatabilityV03525Tests(unittest.TestCase):
    def test_three_run_unstable_not_defaultable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = [root / "run1", root / "run2", root / "run3"]
            _write_run(runs[0], "PASS")
            _write_run(runs[1], "FAILED")
            _write_run(runs[2], "FAILED")
            summary = build_residual_revision_repeatability_v0_35_25(run_dirs=runs, out_dir=root / "out")
            self.assertEqual(summary["pass_counts"], [1, 0, 0])
            self.assertEqual(summary["decision"], "residual_revision_positive_but_unstable_not_defaultable")


if __name__ == "__main__":
    unittest.main()
