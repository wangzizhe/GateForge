from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_strategy_card_live_attribution_v0_33_6 import (
    build_strategy_card_live_attribution,
)


def _write_result(root: Path, *, success: bool, submitted: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps({"version": "v0.33.5"}), encoding="utf-8")
    result = 'resultFile = "/workspace/X_res.mat"' if success else "failed"
    row = {
        "case_id": "case_a",
        "final_verdict": "PASS" if submitted else "FAILED",
        "submitted": submitted,
        "token_used": 10,
        "step_count": 2,
        "steps": [
            {
                "step": 1,
                "tool_calls": [
                    {
                        "name": "check_model",
                        "arguments": {
                            "model_text": "model X connector Pin flow Real i; end Pin; Pin p[2]; equation connect(p[1], p[2]); end X;"
                        },
                    }
                ],
                "tool_results": [{"name": "check_model", "result": result}],
            }
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class StrategyCardLiveAttributionV0336Tests(unittest.TestCase):
    def test_classifies_success_without_submit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_result(root, success=True, submitted=False)
            summary = build_strategy_card_live_attribution(run_dir=root, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["success_without_submit_count"], 1)
            self.assertEqual(summary["decision"], "strategy_card_probe_mixes_discovery_and_submit_budget_failures")
            self.assertFalse(summary["discipline"]["auto_submit_added"])

    def test_classifies_discovery_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_result(root, success=False, submitted=False)
            summary = build_strategy_card_live_attribution(run_dir=root, out_dir=root / "out")
            self.assertEqual(summary["candidate_discovery_failure_count"], 1)


if __name__ == "__main__":
    unittest.main()
