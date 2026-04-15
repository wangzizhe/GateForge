from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_live_executor_v1 import _parse_main_args

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_capability_attribution_report_v0_19_8 import (  # noqa: E402
    NONLOCAL_REASONING_DEFINITION,
    classify_resolution_mechanism,
    reasoning_case_admission_criterion,
    v0_19_9_candidate_shortlist,
)


class V0198CapabilityAttributionTests(unittest.TestCase):
    def test_executor_accepts_disable_bounded_residual_repairs_flag(self) -> None:
        argv = [
            "agent_modelica_live_executor_v1.py",
            "--disable-bounded-residual-repairs",
            "on",
        ]

        with patch.object(sys, "argv", argv):
            args = _parse_main_args()

        self.assertEqual(args.disable_bounded_residual_repairs, "on")

    def test_counterfactual_failure_marks_heuristic_dependency(self) -> None:
        normal = {"executor_status": "PASS", "n_turns": 2}
        counterfactual = {"executor_status": "FAILED", "n_turns": 8}

        mechanism = classify_resolution_mechanism(normal, counterfactual)

        self.assertEqual(mechanism, "executor_heuristic_dependent")

    def test_counterfactual_turn_increase_marks_assisted_not_required(self) -> None:
        normal = {"executor_status": "PASS", "n_turns": 2}
        counterfactual = {"executor_status": "PASS", "n_turns": 4}

        mechanism = classify_resolution_mechanism(normal, counterfactual)

        self.assertEqual(mechanism, "heuristic_assisted_but_not_required")

    def test_counterfactual_equal_turns_marks_local_or_surface_repair(self) -> None:
        normal = {"executor_status": "PASS", "n_turns": 2}
        counterfactual = {"executor_status": "PASS", "n_turns": 2}

        mechanism = classify_resolution_mechanism(normal, counterfactual)

        self.assertEqual(mechanism, "llm_local_or_surface_repair")

    def test_admission_criterion_freezes_operational_nonlocal_definition(self) -> None:
        criterion = reasoning_case_admission_criterion()
        hard_constraint_ids = {item["id"] for item in criterion["hard_constraints"]}

        self.assertEqual(criterion["status"], "frozen")
        self.assertEqual(
            criterion["requires_nonlocal_or_semantic_reasoning_definition"],
            NONLOCAL_REASONING_DEFINITION,
        )
        self.assertIn("no_known_heuristic_solvable", hard_constraint_ids)
        self.assertIn("failure_localization_not_explicit_tag", hard_constraint_ids)
        self.assertIn("requires_nonlocal_or_semantic_reasoning", hard_constraint_ids)

    def test_v0199_shortlist_is_reasoning_family_only(self) -> None:
        shortlist = v0_19_9_candidate_shortlist()

        self.assertGreaterEqual(len(shortlist), 3)
        self.assertTrue(all("reason" in item for item in shortlist))
        self.assertTrue(
            any(item["family"] == "semantic_initial_value_wrong_but_compiles" for item in shortlist)
        )


if __name__ == "__main__":
    unittest.main()
