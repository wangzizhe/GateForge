from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_engineering_mutation_screening_v0_22_1 import (
    build_repair_case,
    build_repair_cases,
    classify_screening_result,
    run_engineering_mutation_screening,
)


def _admitted_row(candidate_id: str = "v0220_a") -> dict:
    return {
        "candidate_id": candidate_id,
        "mutation_pattern": "measurement_abstraction_residual",
        "source_model_path": "/tmp/source.mo",
        "target_model_path": "/tmp/target.mo",
        "target_bucket_id": "ET03",
        "target_admission_status": "admitted_engineering_mutation_failure",
        "impact_points": ["hidden"],
        "workflow_intent": "hidden",
    }


def _payload(status: str, observed: list[str], *, repair_rounds: int = 0) -> dict:
    return {
        "executor_status": status,
        "attempts": [
            {
                "observed_failure_type": item,
                **(
                    {"declaration_fix_repair": {"applied": True}}
                    if index < repair_rounds
                    else {}
                ),
            }
            for index, item in enumerate(observed)
        ],
        "remedy_pack_enabled": False,
        "capability_intervention_pack_enabled": False,
        "broader_change_pack_enabled": False,
        "experience_replay": {"used": False},
        "planner_experience_injection": {"used": False},
    }


class EngineeringMutationScreeningV0221Tests(unittest.TestCase):
    def test_build_repair_case_omits_hidden_mutation_metadata(self) -> None:
        case = build_repair_case(_admitted_row())

        self.assertIsNotNone(case)
        assert case is not None
        self.assertEqual(case["benchmark_family"], "engineering_refactor_residual")
        self.assertNotIn("impact_points", case)
        self.assertNotIn("workflow_intent", case)
        self.assertNotIn("residual_shape", case)

    def test_build_repair_cases_skips_non_admitted_rows(self) -> None:
        rows = [_admitted_row("a"), {**_admitted_row("b"), "target_admission_status": "rejected"}]

        cases = build_repair_cases(rows)

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["candidate_id"], "a")

    def test_classify_screening_result_requires_multiple_repair_rounds_for_true_multiturn(self) -> None:
        easy = classify_screening_result(_payload("PASS", ["model_check_error"]), max_rounds=4)
        single_repair = classify_screening_result(
            _payload("PASS", ["model_check_error", "none"], repair_rounds=1), max_rounds=4
        )
        multiturn = classify_screening_result(
            _payload("PASS", ["model_check_error", "simulate_error", "none"], repair_rounds=2), max_rounds=4
        )
        dead = classify_screening_result(
            _payload("FAILED", ["model_check_error", "model_check_error", "model_check_error", "model_check_error"]),
            max_rounds=4,
        )

        self.assertEqual(easy["sample_quality"], "single_turn_easy")
        self.assertEqual(single_repair["sample_quality"], "single_repair_then_validate")
        self.assertEqual(single_repair["repair_round_count"], 1)
        self.assertEqual(multiturn["sample_quality"], "multi_turn_useful")
        self.assertEqual(multiturn["repair_round_count"], 2)
        self.assertEqual(dead["sample_quality"], "dead_end_hard")

    def test_run_engineering_mutation_screening_writes_incremental_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            admission_path = root / "admitted.jsonl"
            out_dir = root / "out"
            admission_path.write_text(
                "\n".join(json.dumps(_admitted_row(f"case_{i}")) for i in range(2)),
                encoding="utf-8",
            )

            def fake_executor(case: dict, _out_path: Path) -> dict:
                if case["candidate_id"] == "case_0":
                    return _payload("PASS", ["model_check_error"])
                return _payload("PASS", ["model_check_error", "none"], repair_rounds=1)

            report = run_engineering_mutation_screening(
                admission_path=admission_path,
                out_dir=out_dir,
                max_rounds=4,
                executor=fake_executor,
            )

            self.assertEqual(report["aggregate"]["total_cases"], 2)
            self.assertEqual(report["aggregate"]["sample_quality_counts"]["single_turn_easy"], 1)
            self.assertEqual(report["aggregate"]["sample_quality_counts"]["single_repair_then_validate"], 1)
            self.assertEqual(report["aggregate"]["multi_turn_useful_count"], 0)
            self.assertTrue((out_dir / "admitted_cases.jsonl").exists())
            self.assertTrue((out_dir / "case_summaries.jsonl").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
