from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_multi_round_promotion_summary_v0_3_4 import (
    build_multi_round_promotion_summary,
)


class AgentModelicaMultiRoundPromotionSummaryV034Tests(unittest.TestCase):
    def test_build_multi_round_promotion_summary_marks_promotion_ready(self) -> None:
        payload_a = {
            "task_id": "case_a",
            "failure_type": "coupled_conflict_failure",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "resolution_path": "deterministic_rule_only",
            "live_request_count": 0,
            "rounds_used": 2,
            "attempts": [
                {"check_model_pass": False, "simulate_pass": False},
                {"check_model_pass": True, "simulate_pass": True, "source_repair": {"applied": True}},
            ],
        }
        payload_b = {
            "task_id": "case_b",
            "failure_type": "cascading_structural_failure",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "resolution_path": "deterministic_rule_only",
            "live_request_count": 0,
            "rounds_used": 2,
            "attempts": [
                {"check_model_pass": True, "simulate_pass": False},
                {"check_model_pass": True, "simulate_pass": True, "source_repair": {"applied": True}},
            ],
        }
        with tempfile.TemporaryDirectory(prefix="gf_v034_promotion_") as td:
            input_dir = Path(td) / "inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "a.json").write_text(json.dumps(payload_a), encoding="utf-8")
            (input_dir / "b.json").write_text(json.dumps(payload_b), encoding="utf-8")
            summary = build_multi_round_promotion_summary(
                validation_input_path=str(input_dir),
                out_dir=str(Path(td) / "out"),
            )
        self.assertEqual(summary.get("status"), "PROMOTION_READY")
        self.assertTrue((summary.get("decision") or {}).get("promote"))


if __name__ == "__main__":
    unittest.main()
