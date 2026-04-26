from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_product_workflow_smoke_v0_26_5 import build_product_workflow_smoke


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ProductWorkflowSmokeV0265Tests(unittest.TestCase):
    def test_product_workflow_smoke_closes_artifact_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {
                "observation_contract": root / "observation.json",
                "provider_profile_matrix": root / "profile.json",
                "run_mode_matrix": root / "run_mode.json",
                "harness_regression_ab": root / "regression.json",
                "golden_smoke_pack": root / "golden.json",
                "replay_harness": root / "replay.json",
            }
            for name, path in inputs.items():
                payload = {"status": "PASS"}
                if name == "run_mode_matrix":
                    payload["run_modes"] = {
                        "smoke": {
                            "purpose": "transport_and_contract_sanity",
                            "may_report_pass_rate": False,
                        }
                    }
                _write_json(path, payload)
            summary = build_product_workflow_smoke(input_paths=inputs, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "product_workflow_smoke_chain_closed")
            self.assertFalse(summary["smoke_policy"]["capability_metric_reported"])
            self.assertTrue(summary["artifact_closure"]["replay_artifact_present"])

    def test_smoke_mode_cannot_report_pass_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {}
            for name in (
                "observation_contract",
                "provider_profile_matrix",
                "harness_regression_ab",
                "golden_smoke_pack",
                "replay_harness",
            ):
                path = root / f"{name}.json"
                _write_json(path, {"status": "PASS"})
                inputs[name] = path
            run_mode = root / "run_mode.json"
            _write_json(
                run_mode,
                {
                    "status": "PASS",
                    "run_modes": {
                        "smoke": {
                            "purpose": "transport_and_contract_sanity",
                            "may_report_pass_rate": True,
                        }
                    },
                },
            )
            inputs["run_mode_matrix"] = run_mode
            summary = build_product_workflow_smoke(input_paths=inputs, out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
