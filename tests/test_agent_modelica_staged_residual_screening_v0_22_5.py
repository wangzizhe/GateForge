from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_staged_residual_screening_v0_22_5 import (
    build_repair_case,
    build_repair_cases,
    run_staged_residual_screening,
)


def _admitted_row(candidate_id: str = "v0224_a") -> dict:
    return {
        "candidate_id": candidate_id,
        "mutation_pattern": "staged_parameter_and_phantom_residual",
        "source_model_path": "/tmp/source.mo",
        "target_model_path": "/tmp/target.mo",
        "target_bucket_id": "ET03",
        "target_admission_status": "admitted_staged_residual_failure",
        "stage_residuals": ["hidden"],
        "staging_hypothesis": "hidden",
    }


def _payload(status: str, repair_rounds: int, attempts: int) -> dict:
    rows = []
    for index in range(attempts):
        row = {"observed_failure_type": "model_check_error" if index + 1 < attempts else "none"}
        if index < repair_rounds:
            row["declaration_fix_repair"] = {"applied": True, "err": "", "provider": "gemini"}
        rows.append(row)
    return {
        "executor_status": status,
        "attempts": rows,
        "remedy_pack_enabled": False,
        "capability_intervention_pack_enabled": False,
        "broader_change_pack_enabled": False,
        "experience_replay": {"used": False},
        "planner_experience_injection": {"used": False},
    }


class StagedResidualScreeningV0225Tests(unittest.TestCase):
    def test_build_repair_case_omits_staged_metadata(self) -> None:
        case = build_repair_case(_admitted_row())

        self.assertIsNotNone(case)
        assert case is not None
        self.assertEqual(case["benchmark_family"], "staged_residual_true_multiturn_candidate")
        self.assertNotIn("stage_residuals", case)
        self.assertNotIn("staging_hypothesis", case)

    def test_build_repair_cases_skips_non_admitted(self) -> None:
        rows = [_admitted_row("a"), {**_admitted_row("b"), "target_admission_status": "rejected"}]

        cases = build_repair_cases(rows)

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["candidate_id"], "a")

    def test_run_staged_residual_screening_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            admission_path = root / "admitted.jsonl"
            out_dir = root / "out"
            admission_path.write_text(json.dumps(_admitted_row("case_0")) + "\n", encoding="utf-8")

            def fake_executor(_case: dict, _out_path: Path) -> dict:
                return _payload("PASS", repair_rounds=2, attempts=3)

            report = run_staged_residual_screening(
                admission_path=admission_path,
                out_dir=out_dir,
                max_rounds=4,
                executor=fake_executor,
            )

            self.assertEqual(report["aggregate"]["multi_turn_useful_count"], 1)
            self.assertTrue((out_dir / "admitted_cases.jsonl").exists())
            self.assertTrue((out_dir / "case_summaries.jsonl").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
