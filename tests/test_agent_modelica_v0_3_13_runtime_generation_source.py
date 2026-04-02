from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_v0_3_13_runtime_generation_source import (
    build_runtime_generation_source,
)


class AgentModelicaV0313RuntimeGenerationSourceTests(unittest.TestCase):
    def test_builds_sources_with_known_good_and_preview_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = root / "runtime.json"
            runtime.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "seed_case",
                                "model_hint": "ExampleModel",
                                "source_model_path": "seed.mo",
                                "source_library": "TestLib",
                                "runtime_recovery_parameter_names": ["R", "C"],
                                "v0_3_13_family_id": "runtime_family",
                                "course_stage": "three_step_runtime_curriculum",
                                "preview_contract": {
                                    "residual_signal_cluster_id": "runtime_parameter_recovery",
                                    "post_rule_residual_stage": "stage_5_runtime_numerical_instability",
                                    "post_rule_residual_error_type": "numerical_instability",
                                    "post_rule_residual_reason": "division by zero",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            specs = [
                {
                    "task_id": "seed_case",
                    "model_name": "ExampleModel",
                    "source_model_path": "seed.mo",
                    "source_library": "TestLib",
                    "model_text": """\
model ExampleModel
  parameter Real R = 100.0;
  parameter Real C = 0.001;
  parameter Real G = 5.0;
equation
end ExampleModel;""",
                }
            ]
            with patch(
                "gateforge.agent_modelica_v0_3_13_runtime_generation_source.CANDIDATE_SPECS",
                specs,
            ):
                payload = build_runtime_generation_source(
                    runtime_taskset_path=str(runtime),
                    out_dir=str(root / "out"),
                )

            self.assertEqual(payload["source_count"], 1)
            self.assertEqual(payload["pair_status_counts"]["validated_runtime_seed"], 1)
            self.assertEqual(payload["pair_status_counts"]["requires_preview"], 2)
            source = payload["sources"][0]
            self.assertEqual(source["known_good_param_pair"], ["R", "C"])
            self.assertEqual(source["allowed_hidden_base_operator"], "paired_value_collapse")


if __name__ == "__main__":
    unittest.main()
