from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_boundary_tool_use_baseline_v0_29_2 import (
    _attach_external_context,
    load_boundary_cases,
    run_boundary_tool_use_baseline,
    task_to_tool_use_case,
)


def _task(case_id: str = "boundary_test_001") -> dict:
    return {
        "case_id": case_id,
        "task_type": "repair",
        "title": "Repair measurement interface",
        "difficulty": "complex",
        "source_backed": True,
        "description": "A measurement interface refactor was partially applied.",
        "initial_model": (
            "model BoundaryTest\n"
            "  Real x;\n"
            "equation\n"
            "end BoundaryTest;\n"
        ),
        "constraints": ["Keep model name unchanged."],
        "verification": {
            "check_model": True,
            "simulate": {"stop_time": 0.2, "intervals": 200},
            "behavioral": {"type": "time_constant", "expected_tau": 0.1, "tolerance": 0.08},
        },
    }


class BoundaryToolUseBaselineV0292Tests(unittest.TestCase):
    def test_task_to_tool_use_case_preserves_final_simulation_budget(self) -> None:
        case = task_to_tool_use_case(_task())
        self.assertEqual(case["model_name"], "BoundaryTest")
        self.assertEqual(case["final_stop_time"], 0.2)
        self.assertEqual(case["final_intervals"], 200)

    def test_load_boundary_cases_filters_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "boundary_test_001.json").write_text(json.dumps(_task()) + "\n", encoding="utf-8")
            (root / "other_test_001.json").write_text(json.dumps(_task("other_test_001")) + "\n", encoding="utf-8")
            cases, errors = load_boundary_cases(task_root=root, case_id_prefix="boundary_")
            self.assertEqual(len(cases), 1)
            self.assertFalse(errors)

    def test_attach_external_context_adds_context_to_cases(self) -> None:
        cases = [task_to_tool_use_case(_task())]
        updated = _attach_external_context(cases, "Modelica context")
        self.assertEqual(updated[0]["external_context"], "Modelica context")
        self.assertNotEqual(id(cases[0]), id(updated[0]))

    def test_run_boundary_tool_use_baseline_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tasks"
            out = Path(tmp) / "out"
            root.mkdir()
            (root / "boundary_test_001.json").write_text(json.dumps(_task()) + "\n", encoding="utf-8")

            def fake_run_tool_use_case(case: dict, **kwargs: object) -> dict:
                return {
                    "case_id": case["case_id"],
                    "final_verdict": "FAILED",
                    "provider_error": "",
                    "steps": [
                        {"tool_calls": [{"name": "check_model", "arguments": {}}]},
                    ],
                }

            with patch(
                "gateforge.agent_modelica_boundary_tool_use_baseline_v0_29_2.run_tool_use_case",
                side_effect=fake_run_tool_use_case,
            ):
                summary = run_boundary_tool_use_baseline(task_root=root, out_dir=out, planner_backend="rule")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["case_count"], 1)
            self.assertEqual(summary["pass_count"], 0)
            self.assertEqual(summary["decision"], "boundary_baseline_has_failures_for_tool_ablation")
            self.assertEqual(summary["tool_call_counts"], {"check_model": 1})
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "results.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
