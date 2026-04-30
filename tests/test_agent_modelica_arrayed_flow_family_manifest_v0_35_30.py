from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_arrayed_flow_family_manifest_v0_35_30 import (
    build_arrayed_flow_family_manifest,
)


class ArrayedFlowFamilyManifestV03530Tests(unittest.TestCase):
    def test_build_manifest_from_private_task_like_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_root = root / "tasks"
            task_root.mkdir()
            payload = {
                "case_id": "sem_x",
                "title": "x",
                "constraints": ["preserve probe"],
                "initial_model": "model X\n connector Pin\n flow Real i; end Pin; partial model B Pin p[2]; end B; replaceable model P = B constrainedby B; equation for i in 1:2 loop connect(a, b); end for; end X;",
            }
            (task_root / "sem_x.json").write_text(json.dumps(payload), encoding="utf-8")
            summary = build_arrayed_flow_family_manifest(
                task_root=task_root,
                case_ids=["sem_x"],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["family_feature_counts"]["arrayed_connectors"], 1)
            self.assertEqual(summary["decision"], "arrayed_connector_flow_family_slice_ready")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_arrayed_flow_family_manifest(
                task_root=root / "missing",
                case_ids=["sem_x"],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
