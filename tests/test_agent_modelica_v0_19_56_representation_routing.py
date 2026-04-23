import tempfile
import unittest
from pathlib import Path

from scripts.run_representation_routing_trajectory_v0_19_56 import (
    build_oracle_existing_summary,
    select_feedback_output,
    select_signal_route,
)


class RepresentationRoutingTests(unittest.TestCase):
    def test_select_feedback_output_uses_check_failure(self):
        stage, output = select_feedback_output(
            check_ok=False,
            check_output="check failed",
            simulate_ok=None,
            simulate_output="",
        )

        self.assertEqual(stage, "check")
        self.assertEqual(output, "check failed")

    def test_select_feedback_output_prefers_richer_failure_output(self):
        stage, output = select_feedback_output(
            check_ok=False,
            check_output="too few equations",
            simulate_ok=False,
            simulate_output="too few equations\nWarning: Variable Tw does not have any remaining equation",
        )

        self.assertEqual(stage, "check_and_simulate")
        self.assertIn("Variable Tw", output)

    def test_select_feedback_output_uses_simulate_failure_after_check_pass(self):
        stage, output = select_feedback_output(
            check_ok=True,
            check_output="check passed",
            simulate_ok=False,
            simulate_output="simulate failed",
        )

        self.assertEqual(stage, "simulate")
        self.assertEqual(output, "simulate failed")

    def test_select_feedback_output_returns_none_after_full_pass(self):
        stage, output = select_feedback_output(
            check_ok=True,
            check_output="check passed",
            simulate_ok=True,
            simulate_output="simulate passed",
        )

        self.assertEqual(stage, "none")
        self.assertEqual(output, "")

    def test_select_signal_route_uses_causal_for_simple_thermal_signal(self):
        mode = select_signal_route(
            candidate_id="v01945_ThermalZone_v0_pp_c1_c2_pv_phi1",
            omc_output="Warning: Variable C1 does not have any remaining equation",
        )

        self.assertEqual(mode, "causal-c5")

    def test_select_signal_route_uses_blt_for_deep_thermal_signal(self):
        mode = select_signal_route(
            candidate_id="v01945_ThermalZone_v0_pp_c1_c3_pv_phi1",
            omc_output=(
                "Warning: Variable C1 does not have any remaining equation\n"
                "Warning: Variable Tw does not have any remaining equation"
            ),
        )

        self.assertEqual(mode, "blt-c5")

    def test_select_signal_route_uses_blt_for_double_flux_phantom(self):
        mode = select_signal_route(
            candidate_id="v01945_SyncMachineSimplified_v0_pp_tpd0__pv_psippd+p",
            omc_output=(
                "Warning: Variable PSIppd_phantom does not have any remaining equation\n"
                "Warning: Variable PSIppq_phantom does not have any remaining equation"
            ),
        )

        self.assertEqual(mode, "blt-c5")

    def test_select_signal_route_defaults_sync_to_baseline(self):
        mode = select_signal_route(
            candidate_id="v01945_SyncMachineSimplified_v0_pp_tpd0__pv_efd+id",
            omc_output="Warning: Variable EFD_phantom does not have any remaining equation",
        )

        self.assertEqual(mode, "baseline-c5")

    def test_select_signal_route_defaults_other_families_to_baseline(self):
        mode = select_signal_route(
            candidate_id="v01945_HydroTurbineGov_v0_pp_r__pv_pmech0+p",
            omc_output="Warning: Variable PMECH does not have any remaining equation",
        )

        self.assertEqual(mode, "baseline-c5")

    def test_build_oracle_existing_summary_from_real_artifacts(self):
        trajectory_dir = Path("artifacts/representation_trajectory_v0_19_56")
        if not trajectory_dir.exists():
            self.skipTest("v0.19.56 representation artifacts are not available")

        summary = build_oracle_existing_summary(trajectory_dir)

        self.assertEqual(summary["case_count"], 8)
        self.assertEqual(summary["pass_count"], 7)
        self.assertAlmostEqual(summary["pass_rate"], 0.875)
        self.assertIn("not a deployable router", summary["note"])

    def test_build_oracle_existing_summary_handles_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            summary = build_oracle_existing_summary(empty)

        self.assertEqual(summary["case_count"], 0)
        self.assertEqual(summary["pass_count"], 0)


if __name__ == "__main__":
    unittest.main()
