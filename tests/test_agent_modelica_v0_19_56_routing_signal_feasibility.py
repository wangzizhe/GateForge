import tempfile
import unittest
from pathlib import Path

from scripts.analyze_routing_signal_feasibility_v0_19_56 import (
    build_analysis,
    classify_feasibility,
    extract_warning_variables,
    write_outputs,
)


class RoutingSignalFeasibilityTests(unittest.TestCase):
    def test_extract_warning_variables_preserves_order_and_deduplicates(self):
        text = (
            "Warning: Variable C1 does not have any remaining equation\n"
            "Warning: Variable Tw does not have any remaining equation\n"
            "Warning: Variable C1 does not have any remaining equation\n"
        )

        self.assertEqual(extract_warning_variables(text), ["C1", "Tw"])

    def test_classify_signal_available_but_not_live_entry(self):
        row = {
            "desired_route": "blt-c5",
            "admission_route": "blt-c5",
            "first_live_route": "causal-c5",
            "live_passed": False,
        }

        self.assertEqual(
            classify_feasibility(row), "signal_available_but_not_at_live_entry"
        )

    def test_classify_route_match_but_generation_failed(self):
        row = {
            "desired_route": "causal-c5",
            "admission_route": "causal-c5",
            "first_live_route": "causal-c5",
            "live_passed": False,
        }

        self.assertEqual(
            classify_feasibility(row), "route_match_but_candidate_generation_failed"
        )

    def test_build_analysis_summarizes_real_artifacts(self):
        strat = Path("artifacts/representation_effect_stratification_v0_19_56/case_stratification.csv")
        routing = Path("artifacts/representation_routing_trajectory_v0_19_56")
        if not strat.exists() or not routing.exists():
            self.skipTest("v0.19.56/v0.19.56 artifacts are not available")

        analysis = build_analysis(stratification_csv=strat, routing_dir=routing)

        self.assertEqual(analysis["case_count"], 8)
        self.assertEqual(analysis["desired_route_case_count"], 7)
        self.assertEqual(analysis["admission_route_match_count"], 3)
        self.assertLess(
            analysis["admission_route_match_count"],
            analysis["desired_route_case_count"],
        )

    def test_write_outputs_creates_report_and_table(self):
        analysis = {
            "version": "v0.19.56",
            "case_count": 1,
            "desired_route_case_count": 1,
            "admission_route_match_count": 1,
            "admission_route_match_rate": 1.0,
            "live_route_match_count": 0,
            "live_route_match_rate": 0.0,
            "feasibility_counts": {"signal_available_but_not_at_live_entry": 1},
            "case_rows": [
                {
                    "candidate_id": "case_a",
                    "model_family": "ThermalZone",
                    "desired_route": "blt-c5",
                    "admission_route": "blt-c5",
                    "first_live_route": "causal-c5",
                    "live_status": "fail",
                    "live_passed": False,
                    "admission_warning_variables": ["C1", "Tw"],
                    "admission_warning_count": 2,
                    "admission_route_matches_desired": True,
                    "live_route_matches_desired": False,
                    "feasibility_class": "signal_available_but_not_at_live_entry",
                }
            ],
            "main_finding": "test",
        }

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_outputs(analysis, out_dir)

            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())
            self.assertTrue((out_dir / "case_signal_audit.csv").exists())


if __name__ == "__main__":
    unittest.main()
