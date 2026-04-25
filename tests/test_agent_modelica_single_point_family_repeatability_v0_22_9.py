from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_single_point_family_repeatability_v0_22_9 import (
    run_family_repeatability,
    summarize_family_repeatability,
)


def _admitted_row(candidate_id: str, family: str = "single_point_capacitor_observability_refactor") -> dict:
    return {
        "candidate_id": candidate_id,
        "mutation_pattern": family,
        "source_model_path": "/tmp/source.mo",
        "target_model_path": "/tmp/target.mo",
        "target_bucket_id": "ET03",
        "target_admission_status": "admitted_single_point_family_failure",
        "source_complexity_class": "small",
    }


def _summary_row(candidate_id: str, family: str, quality: str = "multi_turn_useful", repair_rounds: int = 2) -> dict:
    return {
        "candidate_id": candidate_id,
        "mutation_family": family,
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


class SinglePointFamilyRepeatabilityV0229Tests(unittest.TestCase):
    def test_summarize_family_repeatability_promotes_stable_family(self) -> None:
        family = "single_point_capacitor_observability_refactor"
        rows = [
            {**_summary_row("a", family), "run_id": "ref", "source_complexity_class": "small"},
            {**_summary_row("a", family), "run_id": "repeat", "source_complexity_class": "small"},
        ]

        summary = summarize_family_repeatability(rows)

        self.assertEqual(summary["candidate_stability_counts"]["stable_true_multi"], 1)
        self.assertIn(family, summary["promoted_family_candidates"])

    def test_run_family_repeatability_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            family = "single_point_source_parameterization_refactor"
            admission_path = root / "admitted.jsonl"
            reference_path = root / "reference.jsonl"
            out_dir = root / "out"
            admission_path.write_text(json.dumps(_admitted_row("case_0", family)) + "\n", encoding="utf-8")
            reference_path.write_text(json.dumps(_summary_row("case_0", family)) + "\n", encoding="utf-8")

            def fake_executor(_case: dict, _out_path: Path) -> dict:
                return _payload()

            summary = run_family_repeatability(
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
