from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_substrate_synthesis_v0_25_6 import (
    build_benchmark_substrate_synthesis,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class BenchmarkSubstrateSynthesisV0256Tests(unittest.TestCase):
    def test_build_synthesis_reports_ready_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            payloads = {
                "v0.25.0": {"status": "PASS", "import_status_counts": {}},
                "v0.25.1": {"status": "PASS", "admission_status_counts": {}},
                "v0.25.2": {"status": "PASS", "split_counts": {"positive": 1, "hard_negative": 1, "holdout": 1, "smoke": 1}},
                "v0.25.3": {"status": "PASS", "seed_count": 4, "validation_error_count": 0},
                "v0.25.4": {"status": "PASS", "finding_count": 0},
                "v0.25.5": {"status": "PASS", "failed_gate_count": 0},
            }
            for version, payload in payloads.items():
                path = root / f"{version}.json"
                _write_json(path, payload)
                inputs[version] = path
            summary = build_benchmark_substrate_synthesis(input_paths=inputs, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["ready_for_v0_26_agent_architecture_reintegration"])

    def test_build_synthesis_requires_holdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            for version in ("v0.25.0", "v0.25.1", "v0.25.3", "v0.25.4", "v0.25.5"):
                path = root / f"{version}.json"
                _write_json(path, {"status": "PASS", "validation_error_count": 0, "finding_count": 0, "failed_gate_count": 0})
                inputs[version] = path
            split = root / "v0.25.2.json"
            _write_json(split, {"status": "PASS", "split_counts": {"positive": 1, "hard_negative": 1, "smoke": 1}})
            inputs["v0.25.2"] = split
            summary = build_benchmark_substrate_synthesis(input_paths=inputs, out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
