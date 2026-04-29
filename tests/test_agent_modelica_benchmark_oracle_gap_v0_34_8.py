from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_oracle_gap_v0_34_8 import build_benchmark_oracle_gap


class BenchmarkOracleGapV0348Tests(unittest.TestCase):
    def test_detects_unencoded_reusable_contract_oracle_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "task.json"
            attribution = root / "attr.json"
            task.write_text(
                json.dumps(
                    {
                        "description": "Repair the reusable measurement contract.",
                        "constraints": ["Keep the probe bank behind the replaceable interface."],
                        "verification": {"check_model": True, "simulate": {"stop_time": 0.1}},
                    }
                ),
                encoding="utf-8",
            )
            attribution.write_text(json.dumps({"reusable_contract_concern_count": 1}), encoding="utf-8")
            summary = build_benchmark_oracle_gap(
                task_path=task,
                boundary_attribution_path=attribution,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["oracle_gap_detected"])
            self.assertEqual(summary["decision"], "benchmark_oracle_needs_contract_semantics")
            self.assertTrue(summary["discipline"]["oracle_audit_only"])

    def test_encoded_contract_oracle_blocks_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "task.json"
            attribution = root / "attr.json"
            task.write_text(
                json.dumps(
                    {
                        "description": "Repair the reusable measurement contract.",
                        "constraints": [],
                        "verification": {"check_model": True, "contract": {"kind": "reusable_contract"}},
                    }
                ),
                encoding="utf-8",
            )
            attribution.write_text(json.dumps({"reusable_contract_concern_count": 1}), encoding="utf-8")
            summary = build_benchmark_oracle_gap(
                task_path=task,
                boundary_attribution_path=attribution,
                out_dir=root / "out",
            )
            self.assertFalse(summary["oracle_gap_detected"])


if __name__ == "__main__":
    unittest.main()
