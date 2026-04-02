from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_initialization_generation_source import (
    build_initialization_generation_source,
)


class AgentModelicaV0313InitializationGenerationSourceTests(unittest.TestCase):
    def test_builds_seed_only_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "audit.json"
            candidate_dir = root / "candidates"
            candidate_dir.mkdir()
            audit.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": "seed_init",
                                "residual_signal_cluster_id": "initialization_parameter_recovery",
                                "masking_pattern": "surface_masks_residual",
                                "surface_rule_id": "rule_simulate_error_injection_repair",
                                "first_attempt_stage_subtype": "stage_1_parse_syntax",
                                "second_attempt_stage_subtype": "stage_4_initialization_singularity",
                                "resolution_path": "rule_then_llm",
                                "rounds_used": 3,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (candidate_dir / "seed_init.json").write_text(
                json.dumps(
                    {
                        "task_id": "seed_init",
                        "model_hint": "InitModel",
                        "source_model_path": "init.mo",
                        "source_library": "TestLib",
                        "hidden_base_operator": "init_equation_sign_flip",
                        "source_model_text": "model InitModel\n  Real x(start = 5.0);\ninitial equation\n  x = -(5.0);\nequation\nend InitModel;\n",
                        "mutation_spec": {
                            "hidden_base": {
                                "audit": {
                                    "mutations": [
                                        {"line_index": 3, "lhs": "x", "original_rhs": "5.0", "new_rhs": "-(5.0)"}
                                    ]
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            payload = build_initialization_generation_source(
                audit_summary_path=str(audit),
                candidate_dir=str(candidate_dir),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["source_count"], 1)
            self.assertEqual(payload["preview_queue_count"], 0)
            self.assertEqual(payload["target_status_counts"]["validated_initialization_seed"], 1)
            self.assertEqual(payload["sources"][0]["known_good_lhs"], "x")


if __name__ == "__main__":
    unittest.main()
