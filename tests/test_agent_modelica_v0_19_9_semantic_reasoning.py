from __future__ import annotations

import sys
import unittest
from pathlib import Path

from gateforge.agent_modelica_behavioral_contract_evaluator_v1 import (
    evaluate_behavioral_contract_from_model_text,
)
from gateforge.agent_modelica_l4_guided_search_engine_v1 import (
    apply_source_blind_multistep_llm_plan,
    select_initial_llm_plan_parameters,
    source_blind_multistep_llm_resolution_targets,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_semantic_reasoning_mutations_v0_19_9 import (  # noqa: E402
    SPECS,
    build_model_text,
)
from build_semantic_reasoning_report_v0_19_9 import _llm_selected_fault_parameter  # noqa: E402


class V0199SemanticReasoningTests(unittest.TestCase):
    def test_semantic_product_contract_passes_source_and_fails_mutation(self) -> None:
        spec = SPECS[0]
        source = build_model_text(spec, capacitor=spec.source_capacitor)
        mutated = build_model_text(spec, capacitor=spec.mutated_capacitor)

        source_eval = evaluate_behavioral_contract_from_model_text(
            current_text=source,
            source_model_text=source,
            failure_type="semantic_initial_value_wrong_but_compiles",
        )
        mutated_eval = evaluate_behavioral_contract_from_model_text(
            current_text=mutated,
            source_model_text=source,
            failure_type="semantic_initial_value_wrong_but_compiles",
        )

        self.assertTrue(source_eval["pass"])
        self.assertFalse(mutated_eval["pass"])
        self.assertEqual(mutated_eval["contract_fail_bucket"], "semantic_product_contract_miss")

    def test_llm_target_map_includes_semantic_fault_parameter(self) -> None:
        targets = source_blind_multistep_llm_resolution_targets(
            model_name="V0199SemanticRCSmallV0",
            failure_type="semantic_initial_value_wrong_but_compiles",
        )

        self.assertEqual(targets["C_store"], 0.01)
        self.assertEqual(targets["R_charge"], 100.0)

    def test_semantic_execution_prefers_fault_parameter_when_llm_lists_relation(self) -> None:
        selected = select_initial_llm_plan_parameters(
            llm_plan={"candidate_parameters": ["R_charge", "C_store"]},
            available_targets={"R_charge": 100.0, "C_store": 0.01},
            failure_type="semantic_initial_value_wrong_but_compiles",
        )

        self.assertEqual(selected, ["C_store"])

    def test_semantic_llm_plan_handles_scientific_notation_capacitor(self) -> None:
        text = build_model_text(SPECS[1], capacitor=SPECS[1].mutated_capacitor)

        patched, audit = apply_source_blind_multistep_llm_plan(
            current_text=text,
            declared_failure_type="semantic_initial_value_wrong_but_compiles",
            llm_plan={"candidate_parameters": ["R_charge", "C_store"]},
            llm_reason="semantic_contract_miss",
            parameter_names_override=["C_store"],
        )

        self.assertTrue(audit["applied"])
        self.assertEqual(audit["parameter_names"], ["C_store"])
        self.assertIn("C_store=0.002", patched)

    def test_model_contains_llm_forcing_and_nonlocal_contract_markers(self) -> None:
        text = build_model_text(SPECS[0], capacitor=SPECS[0].mutated_capacitor)

        self.assertIn("gateforge_source_blind_multistep_llm_forcing:true", text)
        self.assertIn("gateforge_semantic_contract_operands: R_charge,C_store", text)
        self.assertIn("gateforge_semantic_contract_target: expectedTimeConstant", text)

    def test_report_detects_llm_fault_parameter_selection(self) -> None:
        payload = {
            "attempts": [
                {
                    "llm_plan_candidate_parameters": ["C_store"],
                    "source_blind_multistep_llm_resolution": {
                        "parameter_names": ["C_store"],
                    },
                }
            ]
        }

        self.assertTrue(_llm_selected_fault_parameter(payload, "C_store"))
        self.assertFalse(_llm_selected_fault_parameter(payload, "R_charge"))


if __name__ == "__main__":
    unittest.main()
