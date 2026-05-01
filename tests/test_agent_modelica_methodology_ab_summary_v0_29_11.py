from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_boundary_tool_use_baseline_v0_29_2 import load_boundary_cases
from gateforge.agent_modelica_methodology_ab_summary_v0_29_11 import build_methodology_ab_summary


def _write_results(path: Path, rows: list[dict]) -> None:
    path.mkdir(parents=True)
    with (path / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _task(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "task_type": "repair",
        "title": "Repair model",
        "difficulty": "complex",
        "source_backed": True,
        "description": "A workflow-proximal repair task.",
        "initial_model": "model X\n  Real x;\nequation\n  x = 1;\nend X;\n",
        "constraints": ["Keep model name unchanged."],
        "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 10}},
    }


class MethodologyABSummaryV02911Tests(unittest.TestCase):
    def test_load_boundary_cases_supports_case_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sem_01.json").write_text(json.dumps(_task("sem_01")) + "\n", encoding="utf-8")
            (root / "repl_01.json").write_text(json.dumps(_task("repl_01")) + "\n", encoding="utf-8")
            cases, errors = load_boundary_cases(task_root=root, case_id_prefix="", case_ids=["repl_01"])
            self.assertFalse(errors)
            self.assertEqual([case["case_id"] for case in cases], ["repl_01"])

    def test_build_methodology_ab_summary_reports_fail_to_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            structural = root / "structural"
            connector = root / "connector"
            _write_results(base, [{"case_id": "sem_03", "final_verdict": "FAILED", "steps": []}])
            _write_results(
                structural,
                [
                    {
                        "case_id": "sem_03",
                        "final_verdict": "PASS",
                        "steps": [{"tool_calls": [{"name": "get_unmatched_vars"}]}],
                    }
                ],
            )
            _write_results(connector, [{"case_id": "sem_03", "final_verdict": "FAILED", "steps": []}])

            summary = build_methodology_ab_summary(
                arm_dirs={"base": base, "structural": structural, "connector": connector},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["group_totals"]["sem"]["fail_to_pass"]["structural"], 1)
            self.assertEqual(summary["overall"]["net_delta"]["structural"], 1)
            self.assertEqual(summary["decision"], "methodology_ab_has_net_positive_delta")
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
