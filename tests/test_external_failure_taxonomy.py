from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_external_failure_taxonomy import build_taxonomy, failure_stage


class ExternalFailureTaxonomyTests(unittest.TestCase):
    def test_failure_stage_detects_common_modelica_failures(self) -> None:
        self.assertEqual(failure_stage("Error: Too few equations."), "model_check_underdetermined")
        self.assertEqual(failure_stage("messages = \"Simulation execution failed\""), "simulate")
        self.assertEqual(failure_stage("Failed to build model: Demo"), "build_or_model_check")

    def test_build_taxonomy_classifies_external_failures(self) -> None:
        pairwise_rows = [
            {
                "case_id": "case_a",
                "bucket": "medium",
                "subject_status": "pass",
                "external_status": "fail",
            },
            {
                "case_id": "case_b",
                "bucket": "hard",
                "subject_status": "fail",
                "external_status": "fail",
            },
            {
                "case_id": "case_c",
                "bucket": "hard",
                "subject_status": "pass",
                "external_status": "pass",
            },
        ]
        external_rows = [
            {"case_id": "case_a", "timed_out": False},
            {"case_id": "case_b", "timed_out": True},
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case_a = root / "case_a"
            case_a.mkdir()
            (case_a / "initial.mo").write_text("model A\nend A;\n", encoding="utf-8")
            (case_a / "final.mo").write_text("model A\nend A;\n", encoding="utf-8")
            (case_a / "final_eval.omc.txt").write_text("Error: Too few equations.", encoding="utf-8")
            case_b = root / "case_b"
            case_b.mkdir()
            (case_b / "initial.mo").write_text("model B\nend B;\n", encoding="utf-8")
            (case_b / "final.mo").write_text("model B\n  Real x;\nend B;\n", encoding="utf-8")

            rows, summary = build_taxonomy(
                pairwise_rows=pairwise_rows,
                external_rows=external_rows,
                workspace_root=root,
                subject_key="subject_status",
            )

        self.assertEqual(summary["failure_count"], 2)
        self.assertEqual(rows[0]["taxonomy"], "unchanged_underdetermined")
        self.assertEqual(rows[1]["taxonomy"], "shared_failure")
        self.assertEqual(summary["shared_failure_case_ids"], ["case_b"])


if __name__ == "__main__":
    unittest.main()
