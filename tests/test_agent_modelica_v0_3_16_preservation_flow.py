from __future__ import annotations

import tempfile
import unittest

from gateforge.agent_modelica_v0_3_16_closeout import build_v0316_closeout
from gateforge.agent_modelica_v0_3_16_preservation_lane_freeze import build_preservation_lane_freeze
from gateforge.agent_modelica_v0_3_16_preservation_mutation_spec import build_preservation_mutation_spec
from gateforge.agent_modelica_v0_3_16_preservation_probe_taskset import build_preservation_probe_taskset
from gateforge.agent_modelica_v0_3_16_residual_preservation_audit import build_residual_preservation_audit


class AgentModelicaV0316PreservationFlowTests(unittest.TestCase):
    def test_audit_reports_round_start_sampling_and_mutation_induced_drift(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = build_residual_preservation_audit(out_dir=d)
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("step_store_sampling_timepoint"), "round_start_residual")
            taxonomy = payload.get("preservation_failure_taxonomy") or {}
            self.assertEqual(taxonomy.get("primary_drift_cause"), "mutation_operation_induced_drift")

    def test_mutation_spec_is_derived_from_audit(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            audit = build_residual_preservation_audit(out_dir=f"{d}/audit")
            spec = build_preservation_mutation_spec(audit_path=f"{d}/audit/summary.json", out_dir=f"{d}/spec")
            self.assertEqual(spec.get("status"), "PASS")
            self.assertIn("paired_value_collapse_with_exactly_two_target_parameters", spec.get("allowed_runtime_operations") or [])
            self.assertIn("multi_target_init_equation_sign_flip", spec.get("disallowed_initialization_operations") or [])

    def test_probe_taskset_uses_historical_success_controls(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = build_preservation_probe_taskset(out_dir=d)
            self.assertEqual(payload.get("status"), "PASS")
            self.assertGreaterEqual(int(payload.get("task_count") or 0), 4)
            first = (payload.get("tasks") or [])[0]
            self.assertTrue(first.get("v0_3_16_expected_stage_subtype"))
            self.assertTrue(first.get("v0_3_16_expected_residual_signal_cluster"))

    def test_lane_freeze_and_closeout_not_ready_on_low_probe_count(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            probe_summary_path = f"{d}/probe_summary.json"
            from pathlib import Path
            import json

            Path(probe_summary_path).write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "probe_admitted_candidate_count": 0,
                        "probe_admitted_rate_pct": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            freeze = build_preservation_lane_freeze(probe_summary_path=probe_summary_path, out_dir=f"{d}/freeze")
            self.assertEqual(freeze.get("lane_status"), "RESIDUAL_PRESERVATION_NOT_READY")


if __name__ == "__main__":
    unittest.main()
