from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_v0_3_17_closeout import build_v0317_closeout
from gateforge.agent_modelica_v0_3_17_common import classify_actionability, failure_type_for_second_run, frozen_prompt_specs
from gateforge.agent_modelica_v0_3_17_distribution_analysis import build_distribution_analysis
from gateforge.agent_modelica_v0_3_17_generation_prompt_pack import build_generation_prompt_pack


class AgentModelicaV0317DistributionFlowTests(unittest.TestCase):
    def test_prompt_pack_freezes_30_active_and_6_reserve(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = build_generation_prompt_pack(out_dir=d)
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("total_active_count") or 0), 30)
            self.assertEqual(int(payload.get("total_reserve_count") or 0), 6)
            frozen = frozen_prompt_specs()
            self.assertEqual(len((frozen.get("simple") or {}).get("active_tasks") or []), 10)
            self.assertEqual(len((frozen.get("complex") or {}).get("reserve_tasks") or []), 2)

    def test_failure_type_and_actionability_helpers_follow_stage(self) -> None:
        failure_type, stage = failure_type_for_second_run({"dominant_stage_subtype": "stage_2_structural_balance_reference"})
        self.assertEqual(failure_type, "model_check_error")
        self.assertEqual(stage, "check")
        self.assertEqual(
            classify_actionability({"dominant_stage_subtype": "stage_1_parse_syntax", "error_subtype": "parse_lexer_error"}),
            "high_actionability",
        )
        self.assertEqual(
            classify_actionability({"dominant_stage_subtype": "stage_2_structural_balance_reference", "error_subtype": "compile_failure_unknown"}),
            "low_actionability",
        )

    def test_distribution_analysis_and_closeout_support_partial_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            generation_path = Path(d) / "generation.json"
            one_step_path = Path(d) / "one_step.json"
            experience_store = Path(d) / "experience_store.json"
            generation_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": "g1",
                                "complexity_tier": "simple",
                                "first_failure": {
                                    "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                                    "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                                    "suggested_actions": ["a"],
                                },
                            },
                            {
                                "task_id": "g2",
                                "complexity_tier": "complex",
                                "first_failure": {
                                    "dominant_stage_subtype": "stage_2_structural_balance_reference",
                                    "residual_signal_cluster": "stage_2_structural_balance_reference|compile_failure_unknown",
                                    "suggested_actions": [],
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            one_step_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": "g1",
                                "complexity_tier": "simple",
                                "second_residual": {
                                    "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                                    "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                                },
                                "second_residual_actionability": "high_actionability",
                            },
                            {
                                "task_id": "g2",
                                "complexity_tier": "complex",
                                "second_residual": {
                                    "dominant_stage_subtype": "stage_9_unknown",
                                    "residual_signal_cluster": "stage_9_unknown|unknown",
                                },
                                "second_residual_actionability": "low_actionability",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            experience_store.write_text(
                json.dumps(
                    {
                        "step_records": [
                            {
                                "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                                "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "gateforge.agent_modelica_v0_3_17_distribution_analysis._build_synthetic_family_keyspace",
                return_value={("stage_5_runtime_numerical_instability", "stage_5_runtime_numerical_instability|division_by_zero")},
            ), mock.patch(
                "gateforge.agent_modelica_v0_3_17_distribution_analysis._build_promoted_multiround_keyspace",
                return_value={("stage_5_runtime_numerical_instability", "stage_5_runtime_numerical_instability|division_by_zero")},
            ):
                analysis = build_distribution_analysis(
                    generation_census_path=str(generation_path),
                    one_step_repair_path=str(one_step_path),
                    experience_store_path=str(experience_store),
                    out_dir=f"{d}/analysis",
                )
            self.assertEqual(analysis.get("version_decision"), "distribution_alignment_partial")
            prompt_pack = Path(d) / "prompt_pack.json"
            prompt_pack.write_text(json.dumps({"status": "PASS", "total_active_count": 30, "total_reserve_count": 6}), encoding="utf-8")
            closeout = build_v0317_closeout(
                prompt_pack_path=str(prompt_pack),
                generation_census_path=str(generation_path),
                one_step_repair_path=str(one_step_path),
                analysis_path=f"{d}/analysis/summary.json",
                out_dir=f"{d}/closeout",
            )
            self.assertEqual(closeout.get("conclusion", {}).get("version_decision"), "distribution_alignment_partial")


if __name__ == "__main__":
    unittest.main()
