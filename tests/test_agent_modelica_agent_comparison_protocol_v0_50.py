from __future__ import annotations

import unittest

from gateforge.agent_modelica_agent_comparison_protocol_v0_50_0 import build_agent_comparison_protocol
from gateforge.agent_modelica_external_agent_result_intake_v0_50_3 import (
    build_external_agent_result_intake_summary,
    validate_external_agent_result,
)
from gateforge.agent_modelica_external_agent_task_bundle_v0_50_2 import build_external_agent_task_bundle
from gateforge.agent_modelica_agent_comparison_pilot_closeout_v0_50_5 import build_agent_comparison_pilot_closeout


class AgentComparisonProtocolV050Tests(unittest.TestCase):
    def test_protocol_uses_paired_design_and_separates_audit_only_info(self) -> None:
        summary = build_agent_comparison_protocol()
        self.assertTrue(summary["paired_design"]["same_case_pairing_required"])
        self.assertIn("hidden_oracle", summary["arm_contracts"]["gateforge"]["audit_only_information"])
        self.assertIn("initial_model", summary["arm_contracts"]["external_agent"]["prompt_visible_information"])

    def test_task_bundle_omits_hidden_oracle_and_reference_solution(self) -> None:
        task = {
            "case_id": "case_a",
            "title": "Task",
            "description": "Repair this model.",
            "constraints": ["Keep model name unchanged."],
            "initial_model": "model Demo end Demo;",
        }
        import tempfile
        from pathlib import Path
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "case_a.json").write_text(json.dumps(task), encoding="utf-8")
            summary, tasks = build_external_agent_task_bundle(case_ids=("case_a",), task_roots=(root,))
        self.assertEqual(summary["status"], "PASS")
        self.assertFalse(summary["leakage_contract"]["contains_hidden_oracle"])
        self.assertNotIn("hidden_oracle", tasks[0])

    def test_result_intake_validates_required_fields(self) -> None:
        errors = validate_external_agent_result({"case_id": "case_a", "final_verdict": "PASS"})
        self.assertIn("missing:agent_name", errors)
        summary = build_external_agent_result_intake_summary(
            rows=[
                {
                    "case_id": "case_a",
                    "agent_name": "external",
                    "llm_model": "model",
                    "final_verdict": "PASS",
                    "omc_invocation_count": 2,
                    "submitted": True,
                    "failure_category": "none",
                }
            ]
        )
        self.assertEqual(summary["status"], "PASS")

    def test_pilot_closeout_waits_for_external_results(self) -> None:
        summary = build_agent_comparison_pilot_closeout(
            protocol={"status": "PASS", "pilot_case_ids": ["case_a"]},
            baseline={"case_count": 3},
            bundle={"status": "PASS", "task_count": 3},
            intake={"status": "REVIEW", "result_count": 0},
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertFalse(summary["external_results_ready"])
        self.assertFalse(summary["comparison_result_available"])


if __name__ == "__main__":
    unittest.main()
