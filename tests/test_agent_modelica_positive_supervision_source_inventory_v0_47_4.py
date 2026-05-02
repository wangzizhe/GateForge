from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_positive_supervision_source_inventory_v0_47_4 import (
    build_positive_supervision_source_inventory,
)


class PositiveSupervisionSourceInventoryV0474Tests(unittest.TestCase):
    def test_inventory_detects_reference_fields_and_successful_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "tasks"
            artifact_dir = root / "artifacts" / "run"
            task_dir.mkdir()
            artifact_dir.mkdir(parents=True)
            (task_dir / "case_a.json").write_text(
                json.dumps({"case_id": "case_a", "reference_diff": "reviewed diff"}),
                encoding="utf-8",
            )
            (artifact_dir / "results.jsonl").write_text(
                json.dumps({"case_id": "case_a", "final_verdict": "PASS", "provider_error": ""}) + "\n",
                encoding="utf-8",
            )
            summary = build_positive_supervision_source_inventory(
                queue_rows=[{"case_id": "case_a"}],
                task_dir=task_dir,
                artifact_root=root / "artifacts",
            )
        self.assertEqual(summary["source_counts"]["task_reference_diff_present"], 1)
        self.assertEqual(summary["source_counts"]["successful_repaired_trajectory_present"], 1)
        self.assertEqual(summary["results"][0]["positive_source_status"], "source_available")

    def test_inventory_marks_missing_positive_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tasks").mkdir()
            (root / "artifacts").mkdir()
            summary = build_positive_supervision_source_inventory(
                queue_rows=[{"case_id": "case_a"}],
                task_dir=root / "tasks",
                artifact_root=root / "artifacts",
            )
        self.assertEqual(summary["source_counts"]["no_positive_source_found"], 1)
        self.assertEqual(summary["results"][0]["positive_source_status"], "missing_positive_source")


if __name__ == "__main__":
    unittest.main()
