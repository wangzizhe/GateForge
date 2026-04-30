from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_base_submit_checkpoint_repeatability_v0_35_5 import (
    build_base_submit_checkpoint_repeatability,
)


def _write_run(path: Path, case_id: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": case_id,
        "final_verdict": "PASS",
        "submitted": True,
        "provider_error": "",
        "step_count": 1,
        "token_used": 5,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "submit_final"}],
                "tool_results": [{"name": "submit_final", "result": '{"status":"submitted"}'}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class BaseSubmitCheckpointRepeatabilityV0355Tests(unittest.TestCase):
    def test_detects_varying_candidate_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "run_a"
            run_b = root / "run_b"
            _write_run(run_a, "case_a")
            _write_run(run_b, "case_b")
            summary = build_base_submit_checkpoint_repeatability(run_dirs=[run_a, run_b], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["total_pass_count"], 2)
            self.assertEqual(summary["stable_pass_case_ids"], [])
            self.assertEqual(
                summary["decision"],
                "base_submit_checkpoint_improves_delivery_but_candidate_discovery_varies",
            )

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_base_submit_checkpoint_repeatability(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
