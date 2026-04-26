from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_round_budget_comparison_v0_27_4 import (
    compare_round_budget_rows,
    run_round_budget_comparison,
)


def _row(case_id: str, verdict: str, rounds: list[tuple[int, bool, bool, str]]) -> dict:
    return {
        "case_id": case_id,
        "final_verdict": verdict,
        "repair_round_count": len(rounds),
        "true_multi_turn": verdict == "PASS" and len(rounds) >= 2,
        "attempts": [
            {
                "round": round_index,
                "llm_called": True,
                "patched_text_present": True,
                "model_changed": changed,
                "check_pass_after_patch": passed,
                "raw_omc_after_patch": raw,
            }
            for round_index, changed, passed, raw in rounds
        ],
    }


class RoundBudgetComparisonV0274Tests(unittest.TestCase):
    def test_compare_detects_regression_and_added_round_stall(self) -> None:
        two_round = [
            _row("a", "PASS", [(1, True, False, "Error: Wrong number of subscripts"), (2, True, True, "Check completed")]),
            _row("b", "FAILED", [(1, True, False, "Error: Wrong number of subscripts"), (2, True, False, "Error: Too few equations")]),
        ]
        three_round = [
            _row("a", "FAILED", [(1, True, False, "Error: Wrong number of subscripts"), (2, True, False, "Error: Too few equations"), (3, False, False, "Error: Too few equations")]),
            _row("b", "FAILED", [(1, True, False, "Error: Wrong number of subscripts"), (2, True, False, "Error: Too few equations"), (3, False, False, "Error: Too few equations")]),
        ]
        comparisons, summary = compare_round_budget_rows(two_round_rows=two_round, three_round_rows=three_round)
        self.assertEqual(summary["decision"], "do_not_promote_three_round_budget")
        self.assertEqual(summary["regressed_count"], 1)
        self.assertEqual(summary["improved_count"], 0)
        self.assertEqual(summary["added_round_stall_count"], 2)
        self.assertEqual(comparisons[0]["pass_delta"], "regressed")

    def test_run_comparison_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two = root / "two.jsonl"
            three = root / "three.jsonl"
            two.write_text(json.dumps(_row("a", "FAILED", [(1, True, False, "Error: Too few equations")])) + "\n", encoding="utf-8")
            three.write_text(json.dumps(_row("a", "FAILED", [(1, True, False, "Error: Too few equations"), (2, False, False, "Error: Too few equations")])) + "\n", encoding="utf-8")
            summary = run_round_budget_comparison(two_round_results=two, three_round_results=three, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "case_comparisons.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
