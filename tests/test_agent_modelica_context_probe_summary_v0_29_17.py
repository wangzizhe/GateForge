from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_context_probe_summary_v0_29_17 import build_context_probe_summary


def _write(path: Path, verdict: str) -> None:
    path.mkdir(parents=True)
    row = {
        "case_id": "sem_06",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [{"tool_calls": [{"name": "check_model"}]}],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ContextProbeSummaryV02917Tests(unittest.TestCase):
    def test_build_summary_reports_no_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            context = root / "context"
            _write(baseline, "FAILED")
            _write(context, "FAILED")
            summary = build_context_probe_summary(
                baseline_dir=baseline,
                context_dir=context,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "modelica_context_no_observed_pass_rate_gain")
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
