from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_minimal_contract_attribution_v0_35_15 import (
    build_minimal_contract_attribution,
)


class MinimalContractAttributionV03515Tests(unittest.TestCase):
    def test_detects_minimal_implemented_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": "sem_24_bridge_probe_transfer_bus",
                "final_verdict": "PASS",
                "submitted": True,
                "final_model_text": "model X\n equation\n  probe.plus[1].i = 0;\n  probe.plus[2].i = 0;\nend X;",
                "steps": [],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_minimal_contract_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["minimal_pass_count"], 1)
            self.assertEqual(summary["decision"], "minimal_contract_guidance_improves_implemented_candidate_granularity")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_minimal_contract_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
