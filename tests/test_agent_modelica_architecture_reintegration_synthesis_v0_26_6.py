from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_architecture_reintegration_synthesis_v0_26_6 import (
    build_architecture_reintegration_synthesis,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ArchitectureReintegrationSynthesisV0266Tests(unittest.TestCase):
    def test_synthesis_closes_when_all_gates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            for version in ("v0.26.0", "v0.26.1", "v0.26.2", "v0.26.3"):
                path = root / f"{version}.json"
                _write_json(path, {"status": "PASS", "decision": f"{version}_ok"})
                inputs[version] = path
            path = root / "v0.26.4.json"
            _write_json(path, {"status": "PASS", "decision": "regression_ok", "capability_metric_changed": False})
            inputs["v0.26.4"] = path
            path = root / "v0.26.5.json"
            _write_json(path, {"status": "PASS", "decision": "product_workflow_smoke_chain_closed"})
            inputs["v0.26.5"] = path
            summary = build_architecture_reintegration_synthesis(input_paths=inputs, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["phase_decision"], "v0.26_architecture_reintegration_can_close")
            self.assertEqual(summary["next_focus"], "small_live_baseline_under_frozen_harness")

    def test_synthesis_reviews_when_regression_changed_capability_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            for version in ("v0.26.0", "v0.26.1", "v0.26.2", "v0.26.3", "v0.26.5"):
                path = root / f"{version}.json"
                payload = {"status": "PASS", "decision": "ok"}
                if version == "v0.26.5":
                    payload["decision"] = "product_workflow_smoke_chain_closed"
                _write_json(path, payload)
                inputs[version] = path
            path = root / "v0.26.4.json"
            _write_json(path, {"status": "PASS", "capability_metric_changed": True})
            inputs["v0.26.4"] = path
            summary = build_architecture_reintegration_synthesis(input_paths=inputs, out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")
            self.assertFalse(summary["phase_gates"]["harness_regression_no_capability_shift"])


if __name__ == "__main__":
    unittest.main()
