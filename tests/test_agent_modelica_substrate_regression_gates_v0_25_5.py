from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_substrate_regression_gates_v0_25_5 import (
    build_substrate_regression_gates,
    evaluate_gate,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class SubstrateRegressionGatesV0255Tests(unittest.TestCase):
    def test_evaluate_gate_flags_replay_diff(self) -> None:
        row = evaluate_gate("replay_harness", {"status": "PASS", "candidate_diff_count": 1, "family_diff_count": 0})
        self.assertEqual(row["status"], "FAIL")

    def test_build_substrate_regression_gates_passes_clean_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            payloads = {
                "substrate_manifest": {"status": "PASS", "validation_error_count": 0},
                "golden_smoke_pack": {"status": "PASS", "validation_error_count": 0},
                "replay_harness": {"status": "PASS", "candidate_diff_count": 0, "family_diff_count": 0},
                "boundary_audit": {"status": "PASS", "finding_count": 0},
            }
            for name, payload in payloads.items():
                path = root / f"{name}.json"
                _write_json(path, payload)
                inputs[name] = path
            summary = build_substrate_regression_gates(input_paths=inputs, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["failed_gate_count"], 0)


if __name__ == "__main__":
    unittest.main()
