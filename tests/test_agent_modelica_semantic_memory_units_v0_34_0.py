from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_memory_units_v0_34_0 import (
    SEMANTIC_MEMORY_UNITS,
    build_semantic_memory_units,
    render_memory_units,
    validate_memory_unit,
)


def _write_success_run(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "final_verdict": "PASS",
        "submitted": True,
        "step_count": 3,
        "token_used": 100,
        "steps": [
            {"tool_calls": [{"name": "check_model"}]},
            {"tool_calls": [{"name": "simulate_model"}]},
            {"tool_calls": [{"name": "submit_final"}]},
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class SemanticMemoryUnitsV0340Tests(unittest.TestCase):
    def test_default_units_validate_without_case_or_patch_leakage(self) -> None:
        for unit in SEMANTIC_MEMORY_UNITS:
            self.assertEqual(validate_memory_unit(unit), [])

    def test_rendered_context_keeps_wrapper_boundary(self) -> None:
        rendered = render_memory_units()
        self.assertIn("The LLM must still write candidates itself.", rendered)
        self.assertIn("The wrapper must not generate patches", rendered)
        self.assertNotIn("sem_19", rendered)
        self.assertNotIn("p[1].i = 0", rendered)

    def test_build_requires_successful_trajectory_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            success = root / "success"
            _write_success_run(success)
            summary = build_semantic_memory_units(out_dir=root / "out", success_run_dirs=[success])
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["successful_trajectory_count"], 1)
            self.assertFalse(summary["discipline"]["exact_patch_exported"])

    def test_rejects_exact_patch_like_unit(self) -> None:
        bad = {
            "unit_id": "bad",
            "boundary": "x",
            "failure_symptoms": ["x"],
            "transferable_strategy": ["set p[1].i = 0"],
            "non_goals": ["x"],
            "evidence_source": "x",
        }
        self.assertIn("forbidden_term:p[1].i = 0", validate_memory_unit(bad))


if __name__ == "__main__":
    unittest.main()
