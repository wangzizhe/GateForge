from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_post_restore_family_spec_v0_3_6 import (
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
    build_lane_summary,
    build_lane_summary_from_taskset,
    check_measurement_protocol_gate,
    check_residual_harder_gate,
    run_admission_gates,
)


def _baseline_protocol() -> dict:
    return {
        "protocol_version": BASELINE_PROTOCOL_VERSION,
        "baseline_lever_name": BASELINE_LEVER_NAME,
        "baseline_reference_version": BASELINE_REFERENCE_VERSION,
        "enabled_policy_flags": {
            "allow_baseline_single_sweep": True,
            "allow_new_multistep_policy": False,
        },
    }


def _candidate(task_id: str, **overrides: object) -> dict:
    payload = {
        "task_id": task_id,
        "v0_3_6_family_id": "post_restore_residual_semantic_conflict",
        "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
        "dual_layer_mutation": True,
        "declared_failure_type": "simulate_error",
        "planner_invoked": True,
        "resolution_path": "rule_then_llm",
        "baseline_measurement_protocol": _baseline_protocol(),
        "single_sweep_outcome": "residual_failure_after_first_correction",
        "post_restore_failure_bucket": "residual_semantic_conflict_after_restore",
    }
    payload.update(overrides)
    return payload


class AgentModelicaPostRestoreFamilySpecV036Tests(unittest.TestCase):
    def test_measurement_protocol_gate_passes_for_expected_baseline(self) -> None:
        passed, reason = check_measurement_protocol_gate(_candidate("t1"))
        self.assertTrue(passed)
        self.assertIn("measurement_protocol_ok", reason)

    def test_measurement_protocol_gate_fails_on_wrong_protocol(self) -> None:
        passed, reason = check_measurement_protocol_gate(
            _candidate("t1", baseline_measurement_protocol={"protocol_version": "wrong"})
        )
        self.assertFalse(passed)
        self.assertIn("protocol_version_mismatch", reason)

    def test_residual_harder_gate_accepts_residual_failure_after_first_correction(self) -> None:
        passed, reason = check_residual_harder_gate(_candidate("t1"))
        self.assertTrue(passed)
        self.assertIn("residual_failure_after_first_correction", reason)

    def test_residual_harder_gate_rejects_single_sweep_resolved(self) -> None:
        passed, reason = check_residual_harder_gate(_candidate("t1", single_sweep_outcome="resolved"))
        self.assertFalse(passed)
        self.assertIn("too_easy", reason)

    def test_admission_gates_pass_for_valid_candidate(self) -> None:
        result = run_admission_gates(_candidate("t1"))
        self.assertTrue(result["passed"])
        self.assertEqual(result["task_id"], "t1")

    def test_lane_summary_freeze_ready_when_thresholds_met(self) -> None:
        rows = [_candidate(f"t{i}") for i in range(10)]
        payload = build_lane_summary(rows)
        self.assertEqual(payload["lane_status"], "FREEZE_READY")
        self.assertEqual(payload["admitted_count"], 10)
        self.assertEqual(payload["composition"]["single_sweep_success_rate_pct"], 0.0)
        self.assertEqual(payload["composition"]["deterministic_only_pct"], 0.0)

    def test_lane_summary_rejects_too_easy_lane(self) -> None:
        rows = [_candidate(f"t{i}", single_sweep_outcome="resolved") for i in range(10)]
        payload = build_lane_summary(rows)
        self.assertEqual(payload["lane_status"], "NEEDS_MORE_GENERATION")
        self.assertEqual(payload["admitted_count"], 0)
        self.assertFalse(payload["threshold_checks"]["harder_than_single_sweep"])
        self.assertEqual(payload["composition"]["single_sweep_success_rate_pct"], 100.0)

    def test_lane_summary_rejects_deterministic_heavy_lane(self) -> None:
        rows = [
            _candidate(f"t{i}", resolution_path="deterministic_rule_only", planner_invoked=True)
            if i < 4 else _candidate(f"t{i}")
            for i in range(10)
        ]
        payload = build_lane_summary(rows)
        self.assertEqual(payload["lane_status"], "ADMISSION_VALID")
        self.assertFalse(payload["threshold_checks"]["composition_ok"])
        self.assertEqual(payload["composition"]["deterministic_only_pct"], 40.0)

    def test_lane_summary_requires_multiple_residual_examples(self) -> None:
        rows = []
        for i in range(10):
            if i < 2:
                rows.append(_candidate(f"t{i}"))
            else:
                rows.append(_candidate(f"t{i}", post_restore_failure_bucket="", single_sweep_outcome=""))
        payload = build_lane_summary(rows)
        self.assertEqual(payload["lane_status"], "ADMISSION_VALID")
        self.assertFalse(payload["threshold_checks"]["residual_progress_ok"])
        self.assertFalse(payload["threshold_checks"]["residual_bucket_ok"])

    def test_build_lane_summary_from_taskset_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_lane_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [_candidate(f"t{i}") for i in range(10)]}), encoding="utf-8")
            payload = build_lane_summary_from_taskset(
                candidate_taskset_path=str(taskset),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["lane_status"], "FREEZE_READY")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
