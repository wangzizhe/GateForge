from __future__ import annotations

import unittest

from gateforge.agent_modelica_hard_core_adjacent_plan_v0_48_0 import build_hard_core_adjacent_plan
from gateforge.agent_modelica_hard_core_adjacent_admission_v0_48_3 import (
    build_hard_core_adjacent_admission,
    classify_admission,
    infer_model_name,
)
from gateforge.agent_modelica_hard_core_adjacent_baseline_plan_v0_48_4 import (
    build_hard_core_adjacent_baseline_plan,
)
from gateforge.agent_modelica_hard_core_adjacent_difficulty_summary_v0_48_7 import (
    build_hard_core_adjacent_difficulty_summary,
    classify_case_difficulty,
)
from gateforge.agent_modelica_hard_core_adjacent_supervision_sync_v0_48_8 import (
    build_hard_core_adjacent_supervision_sync,
)
from gateforge.agent_modelica_hard_core_adjacent_closeout_v0_48_9 import build_hard_core_adjacent_closeout
from gateforge.agent_modelica_hard_core_adjacent_gate_v0_48_2 import build_hard_core_adjacent_gate
from gateforge.agent_modelica_hard_core_adjacent_variants_v0_48_1 import build_hard_core_adjacent_variants


class HardCoreAdjacentVariantsV048Tests(unittest.TestCase):
    def test_plan_selects_three_anchors_and_twelve_variants(self) -> None:
        summary = build_hard_core_adjacent_plan()
        self.assertEqual(summary["anchor_count"], 3)
        self.assertEqual(summary["planned_variant_count"], 12)
        self.assertTrue(summary["construction_contract"]["no_wrapper_repair"])

    def test_variant_builder_balances_anchors(self) -> None:
        summary, variants = build_hard_core_adjacent_variants()
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["variant_count"], 12)
        self.assertEqual(set(summary["anchor_counts"].values()), {4})
        self.assertEqual(len({variant["case_id"] for variant in variants}), 12)

    def test_variants_keep_blind_descriptions(self) -> None:
        _, variants = build_hard_core_adjacent_variants()
        forbidden = ("correct fix", "root cause", "answer is")
        for variant in variants:
            visible = " ".join([variant["description"], " ".join(variant["constraints"])])
            self.assertFalse(any(term in visible.lower() for term in forbidden))

    def test_offline_gate_passes_generated_variants(self) -> None:
        _, variants = build_hard_core_adjacent_variants()
        summary = build_hard_core_adjacent_gate(variants=variants)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["offline_gate_pass_count"], 12)
        self.assertEqual(summary["offline_gate_review_count"], 0)

    def test_admission_classifies_failure_without_claiming_hardness(self) -> None:
        self.assertEqual(classify_admission(True, False, 'record SimulationResult resultFile = ""'), "admitted_simulation_or_build_failure")
        self.assertEqual(classify_admission(True, True, "ok"), "not_admitted_already_passes")
        self.assertEqual(
            classify_admission(False, False, "permission denied while trying to connect to the docker API"),
            "environment_blocked_docker_permission",
        )

    def test_admission_builder_uses_injected_checker(self) -> None:
        _, variants = build_hard_core_adjacent_variants()
        selected = variants[:2]

        def fake_check(_task: dict) -> tuple[bool, bool, str]:
            return True, False, 'record SimulationResult resultFile = ""'

        summary = build_hard_core_adjacent_admission(
            variants=selected,
            passed_case_ids={variant["case_id"] for variant in selected},
            check_fn=fake_check,
        )
        self.assertEqual(summary["admitted_case_count"], 2)
        self.assertFalse(summary["conclusion_allowed"])

    def test_infers_model_name_from_model_text(self) -> None:
        self.assertEqual(infer_model_name("model Demo\nend Demo;"), "Demo")

    def test_baseline_plan_uses_admitted_cases_only(self) -> None:
        _, variants = build_hard_core_adjacent_variants()
        admitted = {variants[0]["case_id"], variants[1]["case_id"]}
        summary, rows = build_hard_core_adjacent_baseline_plan(variants=variants, admitted_case_ids=admitted)
        self.assertEqual(summary["planned_run_count"], 2)
        self.assertEqual({row["case_id"] for row in rows}, admitted)
        self.assertEqual(summary["runner_contract"]["wrapper_repair"], "forbidden")

    def test_difficulty_summary_classifies_repeat_outcomes(self) -> None:
        self.assertEqual(
            classify_case_difficulty([{"final_verdict": "FAILED"}, {"final_verdict": "FAILED"}]),
            "hard_negative_candidate",
        )
        self.assertEqual(
            classify_case_difficulty([{"final_verdict": "FAILED"}, {"final_verdict": "PASS"}]),
            "unstable",
        )

    def test_difficulty_summary_keeps_conclusion_provider_clean(self) -> None:
        import tempfile
        from pathlib import Path
        import json

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(
                json.dumps({"case_id": "case_a", "final_verdict": "FAILED", "provider_error": ""}) + "\n"
                + json.dumps({"case_id": "case_a", "final_verdict": "FAILED", "provider_error": ""}) + "\n",
                encoding="utf-8",
            )
            summary = build_hard_core_adjacent_difficulty_summary(result_paths=[path])
        self.assertEqual(summary["bucket_counts"], {"hard_negative_candidate": 1})
        self.assertTrue(summary["conclusion_allowed"])

    def test_supervision_sync_creates_blank_templates_for_hard_candidates(self) -> None:
        summary, rows = build_hard_core_adjacent_supervision_sync(
            difficulty_summary={
                "results": [
                    {"case_id": "case_a", "difficulty_bucket": "hard_negative_candidate"},
                    {"case_id": "case_b", "difficulty_bucket": "easy"},
                ]
            }
        )
        self.assertEqual(summary["hard_candidate_count"], 1)
        self.assertEqual(rows[0]["case_id"], "case_a")
        self.assertEqual(rows[0]["accepted_next_action_family"], "")

    def test_closeout_promotes_next_registry_step(self) -> None:
        summary = build_hard_core_adjacent_closeout(
            variants={"variant_count": 12},
            admission={"admitted_case_count": 12},
            difficulty={
                "conclusion_allowed": True,
                "bucket_counts": {"hard_negative_candidate": 2},
                "hard_negative_candidate_case_ids": ["case_a", "case_b"],
            },
            supervision={"label_template_row_count": 2},
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["decision"], "promote_hard_candidates_to_next_registry_repeatability_step")


if __name__ == "__main__":
    unittest.main()
