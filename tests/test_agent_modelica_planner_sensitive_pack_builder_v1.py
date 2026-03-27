import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_planner_sensitive_pack_builder_v1 import build_planner_sensitive_pack


class AgentModelicaPlannerSensitivePackBuilderV1Tests(unittest.TestCase):
    def test_build_planner_sensitive_pack_selects_stage3_and_stage4_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_pack = root / "source_pack.json"
            gf_results = root / "gf_results.json"
            out_pack = root / "out_pack.json"
            source_pack.write_text(
                json.dumps(
                    {
                        "pack_label": "Demo Pack",
                        "cases": [
                            {"mutation_id": "a", "expected_failure_type": "model_check_error"},
                            {"mutation_id": "b", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "c", "expected_failure_type": "simulate_error"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            gf_results.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "a",
                                "resolution_attribution": {
                                    "resolution_path": "deterministic_rule_only",
                                    "dominant_stage_subtype": "stage_2_structural_balance_reference",
                                    "planner_invoked": False,
                                },
                            },
                            {
                                "mutation_id": "b",
                                "resolution_attribution": {
                                    "resolution_path": "rule_then_llm",
                                    "dominant_stage_subtype": "stage_3_type_connector_semantic",
                                    "planner_invoked": True,
                                    "planner_used": True,
                                    "llm_request_count": 1,
                                },
                            },
                            {
                                "mutation_id": "c",
                                "resolution_attribution": {
                                    "resolution_path": "llm_planner_assisted",
                                    "dominant_stage_subtype": "stage_4_initialization_singularity",
                                    "planner_invoked": True,
                                    "planner_used": True,
                                    "planner_decisive": True,
                                    "llm_request_count": 2,
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = build_planner_sensitive_pack(
                source_pack_path=str(source_pack),
                gf_results_paths=[str(gf_results)],
                out_pack_path=str(out_pack),
                max_cases=10,
            )

            out_payload = json.loads(out_pack.read_text(encoding="utf-8"))
            selected_ids = [row["mutation_id"] for row in out_payload.get("cases") or []]
            self.assertEqual(selected_ids, ["c", "b"])
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["planner_invoked_rate_pct"], 100.0)

    def test_build_planner_sensitive_pack_marks_low_invocation_rate_as_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_pack = root / "source_pack.json"
            gf_results = root / "gf_results.json"
            out_pack = root / "out_pack.json"
            source_pack.write_text(
                json.dumps({"cases": [{"mutation_id": "a"}, {"mutation_id": "b"}]}),
                encoding="utf-8",
            )
            gf_results.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "a",
                                "resolution_attribution": {
                                    "resolution_path": "rule_then_llm",
                                    "dominant_stage_subtype": "stage_3_type_connector_semantic",
                                    "planner_invoked": True,
                                },
                            },
                            {
                                "mutation_id": "b",
                                "resolution_attribution": {
                                    "resolution_path": "rule_then_llm",
                                    "dominant_stage_subtype": "stage_3_type_connector_semantic",
                                    "planner_invoked": False,
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = build_planner_sensitive_pack(
                source_pack_path=str(source_pack),
                gf_results_paths=[str(gf_results)],
                out_pack_path=str(out_pack),
                max_cases=10,
                planner_invoked_target_pct=75.0,
            )
            self.assertEqual(summary["status"], "NEEDS_REVIEW")
            self.assertEqual(summary["validation_reason"], "planner_invoked_rate_below_target")


if __name__ == "__main__":
    unittest.main()
