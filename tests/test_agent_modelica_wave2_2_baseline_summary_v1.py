import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaWave22BaselineSummaryV1Tests(unittest.TestCase):
    def test_summary_emits_coupling_span_and_difficulty_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "a",
                                "failure_type": "cross_component_parameter_coupling_error",
                                "coupling_span": "cross_component",
                                "repair_triviality_risk": "medium",
                                "trivial_restore_guard": False,
                                "source_dependency_count": 2,
                                "delayed_failure_signal": True,
                            },
                            {
                                "task_id": "b",
                                "failure_type": "mode_switch_guard_logic_error",
                                "coupling_span": "control_loop",
                                "repair_triviality_risk": "low",
                                "trivial_restore_guard": True,
                                "source_dependency_count": 2,
                                "delayed_failure_signal": True,
                            },
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            challenge = root / "challenge.json"
            challenge.write_text(
                json.dumps(
                    {
                        "total_tasks": 2,
                        "counts_by_library": {"liba": 2},
                        "counts_by_failure_type": {
                            "cross_component_parameter_coupling_error": 1,
                            "mode_switch_guard_logic_error": 1,
                        },
                        "counts_by_coupling_span": {"cross_component": 1, "control_loop": 1},
                        "taskset_frozen_path": str(taskset),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            baseline_summary = root / "baseline_summary.json"
            baseline_summary.write_text(json.dumps({"status": "PASS", "success_count": 2, "success_at_k_pct": 100.0}, indent=2), encoding="utf-8")
            results = root / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "a",
                                "passed": True,
                                "rounds_used": 1,
                                "repair_audit": {"diagnostic_error_type": "semantic_regression"},
                                "attempts": [{"stderr_snippet": "The following assertion has been violated during initialization at time 0.000000"}],
                            },
                            {
                                "task_id": "b",
                                "passed": True,
                                "rounds_used": 2,
                                "repair_audit": {"diagnostic_error_type": "simulate_error"},
                                "attempts": [{"stderr_snippet": ""}],
                            },
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_wave2_2_baseline_summary_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(baseline_summary),
                    "--baseline-results",
                    str(results),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("trivial_restore_suspected_count"), 1)
            self.assertEqual(payload.get("trivial_restore_suspected_pct"), 50.0)
            self.assertEqual(payload.get("first_round_pass_count"), 1)
            self.assertEqual(payload.get("first_round_pass_pct"), 50.0)
            self.assertEqual(payload.get("first_round_pass_task_ids"), ["a"])
            self.assertEqual(payload.get("median_repair_rounds"), 0.0)
            self.assertEqual(payload.get("t0_failure_suspected_count"), 1)
            self.assertEqual(payload.get("source_dependency_backed_task_pct"), 100.0)
            self.assertEqual(payload.get("delayed_failure_signal_pct"), 100.0)
            self.assertEqual(payload.get("success_by_coupling_span", {}).get("cross_component", {}).get("success_at_k_pct"), 100.0)


if __name__ == "__main__":
    unittest.main()
