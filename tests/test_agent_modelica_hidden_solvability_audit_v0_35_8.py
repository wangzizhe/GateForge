from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.test_agent_modelica_hard_family_expansion_v0_32_0 import _task

from gateforge.agent_modelica_hidden_solvability_audit_v0_35_8 import build_hidden_solvability_audit


def _runner(_: str, __: str, ___: float, ____: int) -> tuple[int, str, bool, bool]:
    return 0, "ok", True, True


class HiddenSolvabilityAuditV0358Tests(unittest.TestCase):
    def test_build_summary_passes_hidden_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_root = root / "tasks"
            reference_root = root / "refs"
            task_root.mkdir()
            reference_root.mkdir()
            case_id = "sem_22_arrayed_three_branch_probe_bus"
            task = _task(case_id)
            task["initial_model"] = "model Sample\n  Real x;\nend Sample;\n"
            reference = {"case_id": case_id, "reference_model_text": "model Sample\n  Real x;\nequation\n  x = 1;\nend Sample;\n"}
            (task_root / f"{case_id}.json").write_text(json.dumps(task), encoding="utf-8")
            (reference_root / f"{case_id}.json").write_text(json.dumps(reference), encoding="utf-8")
            summary = build_hidden_solvability_audit(
                task_root=task_root,
                reference_root=reference_root,
                out_dir=root / "out",
                case_ids=(case_id,),
                omc_runner=_runner,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["discipline"]["reference_injected_into_prompt"])
            self.assertEqual(summary["rows"][0]["status"], "PASS")

    def test_model_name_change_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_root = root / "tasks"
            reference_root = root / "refs"
            task_root.mkdir()
            reference_root.mkdir()
            case_id = "sem_22_arrayed_three_branch_probe_bus"
            task = _task(case_id)
            task["initial_model"] = "model A\nend A;\n"
            reference = {"case_id": case_id, "reference_model_text": "model B\nend B;\n"}
            (task_root / f"{case_id}.json").write_text(json.dumps(task), encoding="utf-8")
            (reference_root / f"{case_id}.json").write_text(json.dumps(reference), encoding="utf-8")
            summary = build_hidden_solvability_audit(
                task_root=task_root,
                reference_root=reference_root,
                out_dir=root / "out",
                case_ids=(case_id,),
                omc_runner=_runner,
            )
            self.assertEqual(summary["status"], "REVIEW")
            self.assertIn("model_name_changed", summary["rows"][0]["blockers"])


if __name__ == "__main__":
    unittest.main()
