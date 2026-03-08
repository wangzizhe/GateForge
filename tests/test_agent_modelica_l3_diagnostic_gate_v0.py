import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_l3_diagnostic_gate_v0 import evaluate_l3_diagnostic_gate_v0


class AgentModelicaL3DiagnosticGateV0Tests(unittest.TestCase):
    def test_gate_passes_when_all_thresholds_met(self) -> None:
        summary = evaluate_l3_diagnostic_gate_v0(
            {
                "total_attempts": 10,
                "parse_coverage_pct": 100.0,
                "canonical_type_match_rate_pct": 80.0,
                "stage_match_rate_pct": 75.0,
                "low_confidence_rate_pct": 10.0,
            }
        )
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(summary.get("gate_result"), "PASS")
        self.assertEqual(summary.get("reasons"), [])

    def test_gate_fails_when_threshold_below(self) -> None:
        summary = evaluate_l3_diagnostic_gate_v0(
            {
                "total_attempts": 10,
                "parse_coverage_pct": 94.0,
                "canonical_type_match_rate_pct": 69.0,
                "stage_match_rate_pct": 68.0,
                "low_confidence_rate_pct": 5.0,
            }
        )
        self.assertEqual(summary.get("status"), "FAIL")
        reasons = set(summary.get("reasons") or [])
        self.assertIn("parse_coverage_below_threshold", reasons)
        self.assertIn("canonical_type_match_rate_below_threshold", reasons)
        self.assertIn("stage_match_rate_below_threshold", reasons)

    def test_gate_needs_review_when_low_confidence_is_high(self) -> None:
        summary = evaluate_l3_diagnostic_gate_v0(
            {
                "total_attempts": 10,
                "parse_coverage_pct": 98.0,
                "canonical_type_match_rate_pct": 90.0,
                "stage_match_rate_pct": 90.0,
                "low_confidence_rate_pct": 45.0,
            },
            max_low_confidence_rate_pct=30.0,
        )
        self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
        self.assertEqual(summary.get("gate_result"), "NEEDS_REVIEW")
        self.assertIn("low_confidence_rate_above_threshold", set(summary.get("reasons") or []))

    def test_gate_fails_when_attempts_missing(self) -> None:
        summary = evaluate_l3_diagnostic_gate_v0(
            {
                "total_attempts": 0,
                "parse_coverage_pct": 100.0,
                "canonical_type_match_rate_pct": 100.0,
                "stage_match_rate_pct": 100.0,
                "low_confidence_rate_pct": 0.0,
            }
        )
        self.assertEqual(summary.get("status"), "FAIL")
        self.assertIn("diagnostic_attempts_missing", set(summary.get("reasons") or []))

    def test_cli_can_compute_quality_from_run_results_and_taskset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_results = root / "run_results.json"
            taskset = root / "taskset.json"
            out = root / "summary.json"
            run_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "t1",
                                "attempts": [
                                    {
                                        "observed_failure_type": "script_parse_error",
                                        "diagnostic_ir": {
                                            "error_type": "model_check_error",
                                            "error_subtype": "parse_lexer_error",
                                            "stage": "check",
                                            "confidence": 0.9,
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps({"tasks": [{"task_id": "t1", "failure_type": "model_check_error", "expected_stage": "check"}]}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_l3_diagnostic_gate_v0",
                    "--run-results",
                    str(run_results),
                    "--taskset",
                    str(taskset),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(float(payload.get("parse_coverage_pct") or 0.0), 100.0)
            self.assertEqual(float(payload.get("canonical_type_match_rate_pct") or 0.0), 100.0)


if __name__ == "__main__":
    unittest.main()
