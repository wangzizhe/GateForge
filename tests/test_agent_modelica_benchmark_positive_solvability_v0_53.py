from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_positive_solvability_v0_53_0 import (
    build_benchmark_positive_solvability_audit,
    run_benchmark_positive_solvability_audit,
)


class BenchmarkPositiveSolvabilityV053Tests(unittest.TestCase):
    def test_audit_blocks_full_solvable_scoring_when_sources_are_missing(self) -> None:
        summary = build_benchmark_positive_solvability_audit(
            hard_pack_summary={"hard_case_ids": ["hard_a", "hard_b"]},
            source_inventory_summary={"results": [{"case_id": "hard_a", "positive_source_status": "source_available"}]},
            label_gate_summary={"results": []},
        )
        self.assertEqual(summary["positive_evidence_case_count"], 1)
        self.assertEqual(summary["missing_positive_source_case_ids"], ["hard_b"])
        self.assertFalse(summary["benchmark_use"]["full_solvable_scoring_use_allowed"])
        self.assertFalse(summary["benchmark_use"]["training_use_allowed"])

    def test_accepted_labels_can_supply_positive_evidence(self) -> None:
        summary = build_benchmark_positive_solvability_audit(
            hard_pack_summary={"hard_case_ids": ["hard_a"]},
            source_inventory_summary={"results": []},
            label_gate_summary={"results": [{"case_id": "hard_a", "label_status": "PASS"}]},
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertTrue(summary["benchmark_use"]["full_solvable_scoring_use_allowed"])
        self.assertTrue(summary["benchmark_use"]["training_use_allowed"])

    def test_run_audit_writes_missing_case_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hard = root / "hard.json"
            inventory = root / "inventory.json"
            labels = root / "labels.json"
            hard.write_text('{"hard_case_ids":["hard_a"]}', encoding="utf-8")
            inventory.write_text('{"results":[]}', encoding="utf-8")
            labels.write_text('{"results":[]}', encoding="utf-8")
            out = root / "out"
            summary = run_benchmark_positive_solvability_audit(
                hard_pack_path=hard,
                source_inventory_path=inventory,
                label_gate_path=labels,
                out_dir=out,
            )
            self.assertEqual(summary["missing_positive_source_case_ids"], ["hard_a"])
            self.assertTrue((out / "missing_positive_source_case_ids.txt").exists())


if __name__ == "__main__":
    unittest.main()
