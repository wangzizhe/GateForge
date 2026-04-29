from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_reusable_contract_oracle_repeatability_v0_34_11 import (
    build_reusable_contract_oracle_repeatability,
)


def _write_run(root: Path, *, verdict: str, submitted: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": "case_a",
        "final_verdict": verdict,
        "submitted": submitted,
        "provider_error": "",
        "token_used": 10,
        "step_count": 3,
        "steps": [
            {
                "tool_calls": [{"name": "simulate_model"}],
                "tool_results": [{"name": "simulate_model", "result": 'resultFile = "/workspace/X.mat"'}],
            },
            {
                "tool_calls": [{"name": "reusable_contract_oracle_diagnostic"}],
                "tool_results": [
                    {"name": "reusable_contract_oracle_diagnostic", "result": '{"contract_oracle_pass": true}'}
                ],
            },
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ReusableContractOracleRepeatabilityV03411Tests(unittest.TestCase):
    def test_detects_oracle_pass_without_submit_instability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "a"
            run_b = root / "b"
            _write_run(run_a, verdict="PASS", submitted=True)
            _write_run(run_b, verdict="FAILED", submitted=False)
            summary = build_reusable_contract_oracle_repeatability(
                run_dirs=[run_a, run_b],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(summary["success_oracle_without_submit_count"], 1)
            self.assertEqual(summary["decision"], "oracle_resolves_contract_but_submit_timing_remains_unstable")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_reusable_contract_oracle_repeatability(
                run_dirs=[root / "missing"],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
