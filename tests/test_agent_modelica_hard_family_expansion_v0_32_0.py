from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_hard_family_expansion_v0_32_0 import build_hard_family_expansion_summary


def _task(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "task_type": "repair",
        "title": "Repair workflow interface migration",
        "difficulty": "complex",
        "source_backed": True,
        "benchmark_focus": "model_check_structural",
        "description": "A refactor migrated an interface between reusable Modelica components. Repair the contract while preserving the circuit topology.",
        "initial_model": (
            "model Sample\n"
            "  partial model Base\n"
            "    input Real u;\n"
            "    output Real y;\n"
            "  end Base;\n"
            "  model Impl\n"
            "    extends Base;\n"
            "  equation\n"
            "    y = u;\n"
            "  end Impl;\n"
            "  replaceable model Stage = Impl constrainedby Base;\n"
            "  Modelica.Electrical.Analog.Basic.Resistor R[2];\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C;\n"
            "  Modelica.Electrical.Analog.Basic.Ground G;\n"
            "  Stage stage;\n"
            "  Real z;\n"
            "equation\n"
            "  connect(R[1].n, R[2].p);\n"
            "  connect(C.n, G.p);\n"
            "  z = stage.y;\n"
            "end Sample;\n"
        ),
        "constraints": ["Keep the model name unchanged."],
        "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 10}},
    }


class HardFamilyExpansionV0320Tests(unittest.TestCase):
    def test_build_summary_reports_ready_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_ids = (
                "sem_13_arrayed_connector_bus_refactor",
                "sem_14_inherited_probe_adapter_drift",
            )
            for case_id in case_ids:
                (root / f"{case_id}.json").write_text(json.dumps(_task(case_id)), encoding="utf-8")
            summary = build_hard_family_expansion_summary(
                task_root=root,
                out_dir=root / "out",
                case_ids=case_ids,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["task_count"], 2)
            self.assertEqual(summary["boundary_ready_count"], 2)
            self.assertFalse(summary["discipline"]["llm_capability_gain_claimed"])
            self.assertTrue((root / "out" / "summary.json").exists())

    def test_build_summary_flags_missing_private_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_hard_family_expansion_summary(
                task_root=root,
                out_dir=root / "out",
                case_ids=("sem_13_arrayed_connector_bus_refactor",),
            )
            self.assertEqual(summary["status"], "REVIEW")
            self.assertEqual(summary["validation_error_count"], 1)


if __name__ == "__main__":
    unittest.main()
