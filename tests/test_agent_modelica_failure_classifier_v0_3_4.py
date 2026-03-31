from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_failure_classifier_v0_3_4 import (
    build_failure_classifier,
    classify_failure_row,
)


class AgentModelicaFailureClassifierV034Tests(unittest.TestCase):
    def test_classify_infra_failure_record(self) -> None:
        row = {
            "task_id": "claude_case_a",
            "success": False,
            "infra_failure": True,
            "infra_failure_reason": "not logged in /login required",
        }
        payload = classify_failure_row(row)
        self.assertEqual(payload["failure_bucket"], "infra_interruption")

    def test_classify_budget_stop_from_flag(self) -> None:
        row = {
            "mutation_id": "gf_case_a",
            "success": False,
            "budget_exhausted": True,
        }
        payload = classify_failure_row(row)
        self.assertEqual(payload["failure_bucket"], "budget_stop")

    def test_classify_verifier_reject_when_check_passes_but_simulate_fails(self) -> None:
        row = {
            "mutation_id": "gf_case_b",
            "success": False,
            "check_model_pass": True,
            "simulate_pass": False,
            "planner_invoked": True,
        }
        payload = classify_failure_row(row)
        self.assertEqual(payload["failure_bucket"], "verifier_reject")

    def test_classify_patch_invalid_for_planner_path_with_compile_failure(self) -> None:
        row = {
            "mutation_id": "gf_case_c",
            "success": False,
            "resolution_path": "llm_planner_assisted",
            "planner_invoked": True,
            "check_model_pass": False,
        }
        payload = classify_failure_row(row)
        self.assertEqual(payload["failure_bucket"], "patch_invalid")

    def test_build_failure_classifier_summarizes_bucket_counts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_failure_classifier_") as td:
            root = Path(td)
            input_path = root / "results.json"
            input_path.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "case_a",
                                "success": False,
                                "infra_failure": True,
                                "infra_failure_reason": "quota exceeded",
                            },
                            {
                                "mutation_id": "case_b",
                                "success": False,
                                "resolution_path": "rule_then_llm",
                                "planner_invoked": True,
                                "check_model_pass": False,
                            },
                            {
                                "mutation_id": "case_c",
                                "success": False,
                                "check_model_pass": True,
                                "simulate_pass": False,
                            },
                            {
                                "mutation_id": "case_d",
                                "success": True,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_failure_classifier(input_path=str(input_path), out_dir=str(root / "out"))
            metrics = payload["metrics"]
            self.assertEqual(metrics["row_count"], 4)
            self.assertEqual(metrics["success_count"], 1)
            self.assertEqual(metrics["failure_bucket_counts"]["infra_interruption"], 1)
            self.assertEqual(metrics["failure_bucket_counts"]["patch_invalid"], 1)
            self.assertEqual(metrics["failure_bucket_counts"]["verifier_reject"], 1)


if __name__ == "__main__":
    unittest.main()
