from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_hard_benchmark_gate_v0_29_1 import (
    audit_hard_benchmark_task,
    run_hard_benchmark_gate,
)


def _base_task(**overrides: object) -> dict:
    task = {
        "case_id": "hard_boundary_001",
        "task_type": "repair",
        "title": "Refactor RC measurement interface",
        "difficulty": "complex",
        "source_backed": True,
        "description": (
            "A measurement interface refactor was partially applied. "
            "Preserve behavior while restoring a compileable and simulatable Modelica model."
        ),
        "initial_model": (
            "model SampleModel\n"
            "  Modelica.Electrical.Analog.Sources.StepVoltage V1(V=5, startTime=0.1);\n"
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=100);\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.001);\n"
            "  Modelica.Electrical.Analog.Basic.Ground G;\n"
            "  Real measuredVoltage;\n"
            "equation\n"
            "  connect(V1.p, R1.p);\n"
            "  connect(R1.n, C1.p);\n"
            "  connect(C1.n, V1.n);\n"
            "  connect(V1.n, G.p);\n"
            "  measuredVoltage = C1.v;\n"
            "end SampleModel;\n"
        ),
        "constraints": ["Keep model name unchanged.", "Do not remove the measurement interface."],
        "verification": {
            "check_model": True,
            "simulate": {"stop_time": 0.2, "intervals": 100},
            "behavioral": {
                "type": "time_constant",
                "expected_tau": 0.1,
                "tolerance": 0.08,
            },
        },
    }
    task.update(overrides)
    return task


class HardBenchmarkGateV0291Tests(unittest.TestCase):
    def test_boundary_ready_task_passes_gate(self) -> None:
        row = audit_hard_benchmark_task(_base_task())
        self.assertTrue(row["boundary_ready"])
        self.assertEqual(row["blockers"], [])

    def test_leaky_prompt_blocks_boundary_ready(self) -> None:
        task = _base_task(description="Variable p1 is missing an equation. Fix all errors.")
        row = audit_hard_benchmark_task(task)
        self.assertFalse(row["boundary_ready"])
        self.assertIn("root_cause_leaked_in_prompt", row["blockers"])

    def test_missing_behavioral_oracle_blocks_boundary_ready(self) -> None:
        task = _base_task(
            verification={
                "check_model": True,
                "simulate": {"stop_time": 0.2, "intervals": 100},
            }
        )
        row = audit_hard_benchmark_task(task)
        self.assertFalse(row["boundary_ready"])
        self.assertIn("missing_behavioral_oracle", row["blockers"])

    def test_model_check_structural_focus_does_not_require_behavioral_oracle(self) -> None:
        task = _base_task(
            benchmark_focus="model_check_structural",
            description=(
                "A topology refactor changed the constraint structure. "
                "Repair the Modelica model check failure without changing the intended circuit workflow."
            ),
            verification={
                "check_model": True,
                "simulate": {"stop_time": 0.2, "intervals": 100},
            },
        )
        row = audit_hard_benchmark_task(task)
        self.assertTrue(row["boundary_ready"])
        self.assertNotIn("missing_behavioral_oracle", row["blockers"])

    def test_run_gate_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tasks"
            out = Path(tmp) / "out"
            root.mkdir()
            (root / "hard_boundary_001.json").write_text(
                json.dumps(_base_task(), indent=2) + "\n",
                encoding="utf-8",
            )
            summary = run_hard_benchmark_gate(task_root=root, out_dir=out)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["boundary_ready_count"], 1)
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "task_audit.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
