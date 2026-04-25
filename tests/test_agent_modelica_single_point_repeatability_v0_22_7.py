from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_single_point_repeatability_v0_22_7 import (
    run_single_point_repeatability,
    summarize_repeatability,
)


def _admitted_row(candidate_id: str, complexity: str = "small") -> dict:
    return {
        "candidate_id": candidate_id,
        "mutation_pattern": "single_point_resistor_observability_refactor",
        "source_model_path": "/tmp/source.mo",
        "target_model_path": "/tmp/target.mo",
        "target_bucket_id": "ET03",
        "target_admission_status": "admitted_single_point_complex_failure",
        "source_complexity_class": complexity,
    }


def _summary_row(candidate_id: str, quality: str = "multi_turn_useful", repair_rounds: int = 2) -> dict:
    return {
        "candidate_id": candidate_id,
        "mutation_family": "single_point_resistor_observability_refactor",
        "failure_type": "ET03",
        "executor_status": "PASS" if quality == "multi_turn_useful" else "FAILED",
        "sample_quality": quality,
        "repair_round_count": repair_rounds,
        "n_turns": repair_rounds + 1,
        "observed_error_sequence": ["model_check_error", "model_check_error", "none"],
        "remedy_pack_enabled": False,
        "capability_intervention_pack_enabled": False,
        "broader_change_pack_enabled": False,
        "experience_replay_used": False,
        "planner_experience_injection_used": False,
    }


def _payload(status: str = "PASS", repair_rounds: int = 2, attempts: int = 3) -> dict:
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


class SinglePointRepeatabilityV0227Tests(unittest.TestCase):
    def test_summarize_repeatability_marks_stable_true_multi(self) -> None:
        rows = [
            {**_summary_row("a"), "run_id": "ref", "source_complexity_class": "small"},
            {**_summary_row("a"), "run_id": "repeat", "source_complexity_class": "small"},
            {**_summary_row("b", "dead_end_hard", 7), "run_id": "ref", "source_complexity_class": "large"},
        ]

        summary = summarize_repeatability(rows)

        self.assertEqual(summary["candidate_stability_counts"]["stable_true_multi"], 1)
        self.assertEqual(summary["candidate_stability_counts"]["never_true_multi"], 1)

    def test_run_single_point_repeatability_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            admission_path = root / "admitted.jsonl"
            reference_path = root / "reference.jsonl"
            out_dir = root / "out"
            admission_path.write_text(json.dumps(_admitted_row("case_0")) + "\n", encoding="utf-8")
            reference_path.write_text(json.dumps(_summary_row("case_0")) + "\n", encoding="utf-8")

            def fake_executor(_case: dict, _out_path: Path) -> dict:
                return _payload()

            summary = run_single_point_repeatability(
                admission_path=admission_path,
                reference_summary_path=reference_path,
                out_dir=out_dir,
                repeat_count=1,
                max_rounds=4,
                executor=fake_executor,
            )

            self.assertEqual(summary["candidate_stability_counts"]["stable_true_multi"], 1)
            self.assertTrue((out_dir / "repeat_observations.jsonl").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
