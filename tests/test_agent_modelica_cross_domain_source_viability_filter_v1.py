from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_cross_domain_source_viability_filter_v1 import filter_registry


class AgentModelicaCrossDomainSourceViabilityFilterV1Tests(unittest.TestCase):
    def test_filter_registry_rejects_non_viable_source_models(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_a = root / "ModelA.mo"
            model_b = root / "ModelB.mo"
            model_a.write_text("model ModelA end ModelA;", encoding="utf-8")
            model_b.write_text("model ModelB end ModelB;", encoding="utf-8")
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "dataset_open_source_model_intake_v1",
                        "models": [
                            {
                                "model_id": "a",
                                "source_path": str(model_a),
                                "suggested_scale": "small",
                                "source_library_path": "/tmp/lib",
                                "source_package_name": "OpenIPSL",
                                "source_library_model_path": str(model_a),
                                "source_qualified_model_name": "OpenIPSL.Examples.ModelA",
                            },
                            {
                                "model_id": "b",
                                "source_path": str(model_b),
                                "suggested_scale": "large",
                                "source_library_path": "/tmp/lib",
                                "source_package_name": "OpenIPSL",
                                "source_library_model_path": str(model_b),
                                "source_qualified_model_name": "OpenIPSL.Examples.ModelB",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            registry_out = root / "registry_out.json"
            summary_out = root / "summary.json"

            def _fake_run(*, row, **_kwargs):
                if row.get("model_id") == "a":
                    return {
                        "status": "PASS",
                        "reason": "source_model_viable",
                        "check_model_pass": True,
                        "simulate_pass": True,
                        "rc": 0,
                        "stderr_snippet": "",
                    }
                return {
                    "status": "REJECT",
                    "reason": "simulate_failed_on_source_model",
                    "check_model_pass": True,
                    "simulate_pass": False,
                    "rc": 0,
                    "stderr_snippet": "simulation failed",
                }

            with patch(
                "gateforge.agent_modelica_cross_domain_source_viability_filter_v1._run_viability_check",
                side_effect=_fake_run,
            ):
                summary = filter_registry(
                    registry_path=str(registry),
                    registry_out=str(registry_out),
                    out=str(summary_out),
                    extra_model_loads=["OpenIPSL"],
                )

            filtered = json.loads(registry_out.read_text(encoding="utf-8"))
            self.assertEqual(summary["accepted_models"], 1)
            self.assertEqual(summary["rejected_models"], 1)
            self.assertEqual(len(filtered["models"]), 1)
            self.assertEqual(filtered["models"][0]["model_id"], "a")
            self.assertEqual(filtered["models"][0]["source_viability"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
