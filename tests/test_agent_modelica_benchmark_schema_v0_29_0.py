from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_schema_v0_29_0 import (
    build_schema_summary,
    validate_benchmark_task,
)


class BenchmarkSchemaV0290Tests(unittest.TestCase):
    def test_valid_repair_task_passes(self) -> None:
        task = {
            "case_id": "repair_001",
            "task_type": "repair",
            "title": "Fix model",
            "difficulty": "simple",
            "source_backed": True,
            "description": "A broken Modelica model that needs repair.",
            "initial_model": "model X\n  Real y;\nend X;\n",
            "verification": {
                "check_model": True,
                "simulate": {"stop_time": 0.1, "intervals": 100},
            },
        }
        self.assertEqual(validate_benchmark_task(task), [])

    def test_valid_generation_task_passes(self) -> None:
        task = {
            "case_id": "gen_001",
            "task_type": "generation",
            "title": "Create RC circuit",
            "difficulty": "medium",
            "source_backed": True,
            "description": "Create a Modelica model of an RC circuit with R=100.",
            "initial_model": "",
            "verification": {
                "check_model": True,
                "simulate": {"stop_time": 1.0, "intervals": 500},
                "behavioral": {"type": "time_constant", "expected_tau": 1.0, "tolerance": 0.08},
            },
        }
        self.assertEqual(validate_benchmark_task(task), [])

    def test_missing_required_field(self) -> None:
        task = {"case_id": "x"}
        errors = validate_benchmark_task(task)
        self.assertIn("missing_required:task_type", errors)

    def test_invalid_task_type(self) -> None:
        task = {
            "case_id": "x_001",
            "task_type": "invalid_type",
            "title": "X",
            "difficulty": "simple",
            "source_backed": False,
            "description": "A test case.",
            "initial_model": "",
            "verification": {"check_model": True},
        }
        errors = validate_benchmark_task(task)
        self.assertIn("invalid_task_type:invalid_type", errors)

    def test_invalid_difficulty(self) -> None:
        task = {
            "case_id": "x_001",
            "task_type": "repair",
            "title": "X",
            "difficulty": "impossible",
            "source_backed": False,
            "description": "A test case.",
            "initial_model": "",
            "verification": {"check_model": True},
        }
        errors = validate_benchmark_task(task)
        self.assertIn("invalid_difficulty:impossible", errors)

    def test_description_too_short(self) -> None:
        task = {
            "case_id": "x_001",
            "task_type": "repair",
            "title": "X",
            "difficulty": "simple",
            "source_backed": False,
            "description": "Hi",
            "initial_model": "",
            "verification": {"check_model": True},
        }
        errors = validate_benchmark_task(task)
        self.assertIn("description_too_short", errors)

    def test_invalid_case_id(self) -> None:
        task = {
            "case_id": "Invalid-ID!",
            "task_type": "repair",
            "title": "X",
            "difficulty": "simple",
            "source_backed": False,
            "description": "A test case description.",
            "initial_model": "",
            "verification": {"check_model": True},
        }
        errors = validate_benchmark_task(task)
        self.assertIn("invalid_case_id:Invalid-ID!", errors)

    def test_invalid_behavioral_type(self) -> None:
        task = {
            "case_id": "x_001",
            "task_type": "repair",
            "title": "X",
            "difficulty": "simple",
            "source_backed": False,
            "description": "A test case.",
            "initial_model": "",
            "verification": {
                "check_model": True,
                "behavioral": {"type": "magic"},
            },
        }
        errors = validate_benchmark_task(task)
        self.assertIn("invalid_behavioral_type:magic", errors)

    def test_source_backed_must_be_bool(self) -> None:
        task = {
            "case_id": "x_001",
            "task_type": "repair",
            "title": "X",
            "difficulty": "simple",
            "source_backed": "yes",
            "description": "A test case.",
            "initial_model": "",
            "verification": {"check_model": True},
        }
        errors = validate_benchmark_task(task)
        self.assertIn("source_backed_must_be_bool", errors)

    def test_build_summary_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_schema_summary(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["validation_errors"])
            self.assertTrue((out_dir / "schema.json").exists())


if __name__ == "__main__":
    unittest.main()
