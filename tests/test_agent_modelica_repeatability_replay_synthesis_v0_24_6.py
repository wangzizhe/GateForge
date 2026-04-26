from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_repeatability_replay_synthesis_v0_24_6 import (
    build_repeatability_replay_synthesis,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class RepeatabilityReplaySynthesisV0246Tests(unittest.TestCase):
    def test_build_synthesis_reports_ready_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            payloads = {
                "v0.24.0": {"status": "PASS", "candidate_count": 2, "family_count": 1},
                "v0.24.1": {"status": "PASS"},
                "v0.24.2": {"status": "PASS", "provider_noise_count": 0, "infra_noise_count": 0},
                "v0.24.3": {"status": "PASS", "validation_error_count": 0},
                "v0.24.4": {"status": "PASS", "validation_error_count": 0},
                "v0.24.5": {"status": "PASS", "candidate_diff_count": 0, "family_diff_count": 0},
            }
            for version, payload in payloads.items():
                path = root / f"{version}.json"
                _write_json(path, payload)
                inputs[version] = path

            summary = build_repeatability_replay_synthesis(input_paths=inputs, out_dir=root / "out")

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["ready_for_v0_25_benchmark_substrate_freeze"])

    def test_build_synthesis_flags_replay_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            for version in ("v0.24.0", "v0.24.1", "v0.24.2", "v0.24.3", "v0.24.4"):
                path = root / f"{version}.json"
                _write_json(path, {"status": "PASS", "validation_error_count": 0})
                inputs[version] = path
            replay = root / "v0.24.5.json"
            _write_json(replay, {"status": "PASS", "candidate_diff_count": 1, "family_diff_count": 0})
            inputs["v0.24.5"] = replay

            summary = build_repeatability_replay_synthesis(input_paths=inputs, out_dir=root / "out")

            self.assertEqual(summary["status"], "REVIEW")
            self.assertFalse(summary["ready_for_v0_25_benchmark_substrate_freeze"])


if __name__ == "__main__":
    unittest.main()
