from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_harness_contract_synthesis_v0_23_6 import (
    build_harness_contract_synthesis,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class HarnessContractSynthesisV0236Tests(unittest.TestCase):
    def test_build_harness_contract_synthesis_reports_ready_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs: dict[str, Path] = {}
            payloads = {
                "v0.23.0": {"status": "PASS", "file_inventory": {"summary_count": 4}},
                "v0.23.1": {"status": "PASS", "seed_count": 2},
                "v0.23.2": {"status": "PASS", "trajectory_count": 4},
                "v0.23.3": {"status": "PASS", "oracle_event_count": 8},
                "v0.23.4": {"status": "PASS", "manifest_count": 4},
                "v0.23.5": {"status": "PASS", "total_validation_error_count": 0},
            }
            for version, payload in payloads.items():
                path = root / f"{version}.json"
                _write_json(path, payload)
                inputs[version] = path

            summary = build_harness_contract_synthesis(input_paths=inputs, out_dir=root / "out")

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["ready_for_v0_24_repeatability_replay"])
            self.assertEqual(summary["phase_decision"], "v0.23_harness_contract_freeze_can_close")

    def test_build_harness_contract_synthesis_flags_validator_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs: dict[str, Path] = {}
            for version in ("v0.23.0", "v0.23.1", "v0.23.2", "v0.23.3", "v0.23.4"):
                path = root / f"{version}.json"
                _write_json(path, {"status": "PASS"})
                inputs[version] = path
            validator = root / "v0.23.5.json"
            _write_json(validator, {"status": "PASS", "total_validation_error_count": 1})
            inputs["v0.23.5"] = validator

            summary = build_harness_contract_synthesis(input_paths=inputs, out_dir=root / "out")

            self.assertEqual(summary["status"], "REVIEW")
            self.assertFalse(summary["ready_for_v0_24_repeatability_replay"])


if __name__ == "__main__":
    unittest.main()
