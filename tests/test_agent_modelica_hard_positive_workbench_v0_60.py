from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_hard_positive_workbench_v0_60_0 import (
    build_hard_positive_workbench,
    infer_reference_strategy,
    load_missing_case_ids,
    run_hard_positive_workbench,
)


class HardPositiveWorkbenchV060Tests(unittest.TestCase):
    def test_reference_strategy_groups_probe_and_adapter_cases(self) -> None:
        self.assertEqual(infer_reference_strategy("sem_32_four_segment_adapter_cross_node"), "adapter_contract_reference_repair_required")
        self.assertEqual(infer_reference_strategy("sem_29_two_branch_probe_bus"), "probe_flow_ownership_reference_repair_required")

    def test_build_workbench_keeps_reference_hidden_and_wrapper_forbidden(self) -> None:
        summary = build_hard_positive_workbench(
            missing_case_ids=["case_a"],
            tasks_by_case={
                "case_a": {
                    "case_id": "case_a",
                    "source_backed": True,
                    "initial_model": "model Demo end Demo;",
                    "verification": {"check_model": True},
                    "_source_path": "task.json",
                }
            },
            artifact_root=Path("/no/such/artifacts"),
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertFalse(summary["scope_contract"]["reference_repairs_prompt_visible"])
        self.assertFalse(summary["scope_contract"]["wrapper_repair_allowed"])

    def test_load_missing_case_ids_reads_sorted_nonempty_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.txt"
            path.write_text("b\n\na\n", encoding="utf-8")
            self.assertEqual(load_missing_case_ids(path), ["a", "b"])

    def test_run_workbench_writes_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.txt"
            missing.write_text("case_a\n", encoding="utf-8")
            task_dir = root / "tasks"
            task_dir.mkdir()
            (task_dir / "case_a.json").write_text(
                '{"case_id":"case_a","source_backed":true,"initial_model":"model Demo end Demo;",'
                '"verification":{"check_model":true}}',
                encoding="utf-8",
            )
            out = root / "out"
            summary = run_hard_positive_workbench(
                missing_path=missing,
                task_dirs=(task_dir,),
                task_jsonl_paths=(),
                artifact_root=root / "artifacts",
                out_dir=out,
            )
            self.assertEqual(summary["case_count"], 1)
            self.assertTrue((out / "workbench_cases.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
