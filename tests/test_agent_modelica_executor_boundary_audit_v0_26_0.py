from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_executor_boundary_audit_v0_26_0 import build_executor_boundary_audit


class ExecutorBoundaryAuditV0260Tests(unittest.TestCase):
    def test_build_audit_reports_clean_deepseek_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_executor_boundary_audit(out_dir=Path(tmp) / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["provider_adapter_matrix"]["deepseek_provider_registered"])
            self.assertEqual(
                summary["planner_profile_boundary"]["deepseek_planner_adapter"],
                "gateforge_deepseek_planner_v1",
            )
            self.assertFalse(summary["executor_boundary"]["executor_provider_specific_logic_added"])
            self.assertFalse(summary["adapter_boundary"]["adapter_makes_repair_decisions"])

    def test_build_audit_flags_provider_specific_executor_logic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executor = root / "executor.py"
            adapter = root / "adapter.py"
            planner = root / "planner.py"
            executor.write_text("if provider == 'deepseek':\n    pass\n", encoding="utf-8")
            adapter.write_text("class Adapter: pass\n", encoding="utf-8")
            planner.write_text("def planner(): pass\n", encoding="utf-8")
            summary = build_executor_boundary_audit(
                executor_path=executor,
                adapter_path=adapter,
                planner_path=planner,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")
            self.assertTrue(summary["executor_boundary"]["executor_provider_specific_logic_added"])


if __name__ == "__main__":
    unittest.main()
