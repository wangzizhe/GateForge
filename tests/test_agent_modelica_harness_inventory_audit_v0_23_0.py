from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_harness_inventory_audit_v0_23_0 import (
    build_harness_inventory_audit,
    classify_summary_contract,
    discover_scoped_files,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class HarnessInventoryAuditV0230Tests(unittest.TestCase):
    def test_discover_scoped_files_filters_v0_20_to_v0_22(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for dirname in ("gateforge", "scripts", "tests"):
                (root / dirname).mkdir()
            (root / "gateforge" / "agent_modelica_demo_v0_20_1.py").write_text("", encoding="utf-8")
            (root / "gateforge" / "agent_modelica_demo_v0_19_9.py").write_text("", encoding="utf-8")
            (root / "scripts" / "run_demo_v0_22_3.py").write_text("", encoding="utf-8")
            (root / "tests" / "test_demo_v0_21_0.py").write_text("", encoding="utf-8")

            files = discover_scoped_files(root)

            self.assertEqual(files["modules"], ["gateforge/agent_modelica_demo_v0_20_1.py"])
            self.assertEqual(files["scripts"], ["scripts/run_demo_v0_22_3.py"])
            self.assertEqual(files["tests"], ["tests/test_demo_v0_21_0.py"])

    def test_classify_summary_contract_reports_expected_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "artifacts" / "demo_v0_22_1" / "summary.json"
            _write_json(
                summary_path,
                {
                    "version": "v0.22.1",
                    "aggregate": {"pass_count": 1},
                    "summaries": [{"case_id": "c1", "executor_status": "PASS"}],
                },
            )

            row = classify_summary_contract(summary_path, root)

            self.assertIn("summary_contract_field_drift", row["gaps"])
            self.assertIn("missing_manifest", row["gaps"])
            self.assertIn("trajectory_field_drift", row["gaps"])
            self.assertIn("status", row["missing_target_fields"])

    def test_build_harness_inventory_audit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for dirname in ("gateforge", "scripts", "tests"):
                (root / dirname).mkdir()
            (root / "gateforge" / "agent_modelica_demo_v0_20_1.py").write_text("", encoding="utf-8")
            (root / "scripts" / "run_demo_v0_21_1.py").write_text("", encoding="utf-8")
            (root / "tests" / "test_demo_v0_22_1.py").write_text("", encoding="utf-8")
            _write_json(
                root / "artifacts" / "demo_v0_22_1" / "summary.json",
                {
                    "version": "v0.22.1",
                    "status": "PASS",
                    "analysis_scope": "demo",
                    "conclusion": "demo",
                },
            )
            out_dir = root / "out"

            summary = build_harness_inventory_audit(repo_root=root, out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["file_inventory"]["module_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "artifact_inventory.jsonl").exists())
            self.assertEqual(summary["discipline"]["executor_changes"], "none")


if __name__ == "__main__":
    unittest.main()
