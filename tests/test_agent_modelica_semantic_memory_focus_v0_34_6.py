from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_memory_focus_v0_34_6 import (
    build_semantic_memory_focus,
    select_memory_units,
)


class SemanticMemoryFocusV0346Tests(unittest.TestCase):
    def test_selects_requested_unit_only(self) -> None:
        units = select_memory_units(["arrayed_measurement_flow_ownership"])
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["unit_id"], "arrayed_measurement_flow_ownership")

    def test_build_writes_focused_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_semantic_memory_focus(out_dir=root)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["unit_count"], 1)
            context = (root / "semantic_memory_focus_context.md").read_text(encoding="utf-8")
            self.assertIn("arrayed_measurement_flow_ownership", context)
            self.assertNotIn("standard_library_semantic_substitution", context)
            self.assertTrue(summary["discipline"]["manual_ablation_not_default"])

    def test_missing_unit_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_semantic_memory_focus(out_dir=Path(tmp), unit_ids=["missing"])
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
