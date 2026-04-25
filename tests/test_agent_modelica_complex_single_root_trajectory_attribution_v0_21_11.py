from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_complex_single_root_trajectory_attribution_v0_21_11 import (
    attribute_case,
    build_trajectory_attribution,
    summarize_by_family,
)


def _payload(
    *,
    task_id: str = "v0218_001_measurement_abstraction_partial_M",
    status: str = "PASS",
    observed: list[str] | None = None,
    applied: list[bool] | None = None,
    lengths: list[int] | None = None,
) -> dict:
    observed = observed or ["model_check_error", "constraint_violation", "none"]
    applied = applied if applied is not None else [True, True, False]
    lengths = lengths if lengths is not None else [100, 120]
    attempts = []
    for index, failure in enumerate(observed):
        attempt = {
            "round": index + 1,
            "observed_failure_type": failure,
            "simulate_pass": failure == "none",
            "declaration_fix_repair": {"applied": bool(applied[index]) if index < len(applied) else False},
        }
        if index < len(lengths):
            attempt["candidate_text_checkpoint"] = {"model_text_len": lengths[index]}
        attempts.append(attempt)
    return {
        "task_id": task_id,
        "executor_status": status,
        "remedy_pack_enabled": False,
        "capability_intervention_pack_enabled": False,
        "broader_change_pack_enabled": False,
        "experience_replay": {"used": False},
        "planner_experience_injection": {"used": False},
        "attempts": attempts,
    }


class ComplexSingleRootTrajectoryAttributionV02111Tests(unittest.TestCase):
    def test_attribute_case_marks_multiturn_layer_transition_pass(self) -> None:
        row = attribute_case(_payload())

        self.assertEqual(row["executor_status"], "PASS")
        self.assertEqual(row["failure_attribution"], "repairable_multiturn_layer_transition")
        self.assertTrue(row["saw_layer_transition"])

    def test_attribute_case_marks_low_variation_model_check_stall(self) -> None:
        payload = _payload(
            task_id="v0218_003_namespace_migration_partial_M",
            status="FAILED",
            observed=["model_check_error", "model_check_error", "model_check_error"],
            applied=[True, True, True],
            lengths=[100, 100, 100],
        )

        row = attribute_case(payload)

        self.assertEqual(row["failure_attribution"], "model_check_stall_low_observable_variation")
        self.assertEqual(row["max_same_error_streak"], 3)

    def test_summarize_by_family_counts_pattern_results(self) -> None:
        rows = [
            attribute_case(_payload(task_id="v0218_001_measurement_abstraction_partial_A")),
            attribute_case(
                _payload(
                    task_id="v0218_002_namespace_migration_partial_B",
                    status="FAILED",
                    observed=["model_check_error"],
                    applied=[False],
                    lengths=[],
                )
            ),
        ]

        summary = summarize_by_family(rows)

        self.assertEqual(summary["measurement_abstraction_partial"]["pass_count"], 1)
        self.assertEqual(summary["namespace_migration_partial"]["pass_count"], 0)

    def test_build_trajectory_attribution_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            raw_dir = run_dir / "raw"
            out_dir = root / "out"
            raw_dir.mkdir(parents=True)
            (raw_dir / "case.json").write_text(json.dumps(_payload()), encoding="utf-8")

            summary = build_trajectory_attribution(run_dirs=[run_dir], out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["case_observation_count"], 1)
            self.assertTrue((out_dir / "case_attribution.jsonl").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
