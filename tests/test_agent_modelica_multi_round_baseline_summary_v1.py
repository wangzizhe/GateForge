import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaMultiRoundBaselineSummaryV1Tests(unittest.TestCase):
    def test_summary_emits_round_histogram(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cascading_structural_failure"}, {"task_id": "b", "failure_type": "coupled_conflict_failure"}, {"task_id": "c", "failure_type": "false_friend_patch_trap"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"total_tasks": 3, "counts_by_library": {"liba": 3}, "counts_by_failure_type": {"cascading_structural_failure": 1, "coupled_conflict_failure": 1, "false_friend_patch_trap": 1}, "counts_by_multi_round_family": {"cascade": 1, "coupled_conflict": 1, "false_friend": 1}, "counts_by_expected_rounds_min": {"2": 3}, "cascade_depth_distribution": {"2": 3}, "taskset_frozen_path": str(taskset)}, indent=2), encoding="utf-8")
            baseline_summary = root / "baseline_summary.json"
            baseline_summary.write_text(json.dumps({"status": "PASS", "success_count": 3, "success_at_k_pct": 100.0, "median_repair_rounds": 2.0}, indent=2), encoding="utf-8")
            results = root / "results.json"
            results.write_text(json.dumps({"records": [{"task_id": "a", "passed": True, "rounds_used": 1}, {"task_id": "b", "passed": True, "rounds_used": 2}, {"task_id": "c", "passed": True, "rounds_used": 3}]}, indent=2), encoding="utf-8")
            out = root / "summary.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_baseline_summary_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(baseline_summary), "--baseline-results", str(results), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("first_round_pass_pct"), 33.33)
            self.assertEqual(payload.get("second_round_pass_pct"), 33.33)
            self.assertEqual(payload.get("third_round_pass_pct"), 33.33)
            self.assertEqual(payload.get("round_histogram"), {"1": 1, "2": 1, "3_plus": 1})

    def test_summary_uses_executor_attempts_for_internal_multi_round_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "a", "failure_type": "cascading_structural_failure"},
                            {"task_id": "b", "failure_type": "coupled_conflict_failure"},
                            {"task_id": "c", "failure_type": "false_friend_patch_trap"},
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"total_tasks": 3, "taskset_frozen_path": str(taskset)}, indent=2), encoding="utf-8")
            baseline_summary = root / "baseline_summary.json"
            baseline_summary.write_text(json.dumps({"status": "PASS", "success_count": 3, "success_at_k_pct": 100.0, "median_repair_rounds": 1.0}, indent=2), encoding="utf-8")
            results = root / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "a", "passed": True, "rounds_used": 1, "attempts": [{"round": 1}, {"round": 2}]},
                            {"task_id": "b", "passed": True, "rounds_used": 1, "attempts": [{"round": 1}, {"round": 2}, {"round": 3}]},
                            {"task_id": "c", "passed": True, "rounds_used": 1, "attempts": [{"round": 1}]},
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
                    "gateforge.agent_modelica_multi_round_baseline_summary_v1",
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
            self.assertEqual(payload.get("executor_attempt_histogram"), {"1": 1, "2": 1, "3_plus": 1})
            self.assertEqual(payload.get("executor_first_attempt_pass_pct"), 33.33)
            self.assertEqual(payload.get("executor_second_attempt_pass_pct"), 33.33)
            self.assertEqual(payload.get("executor_third_attempt_pass_pct"), 33.33)
            self.assertEqual(payload.get("median_executor_attempts"), 2.0)

    def test_summary_prefers_nested_executor_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cascading_structural_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"total_tasks": 1, "taskset_frozen_path": str(taskset)}, indent=2), encoding="utf-8")
            baseline_summary = root / "baseline_summary.json"
            baseline_summary.write_text(json.dumps({"status": "PASS", "success_count": 1, "success_at_k_pct": 100.0, "median_repair_rounds": 1.0}, indent=2), encoding="utf-8")
            results = root / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "a",
                                "passed": True,
                                "rounds_used": 1,
                                "attempts": [
                                    {
                                        "round": 1,
                                        "attempts": [{"round": 1}, {"round": 2}, {"round": 3}],
                                    }
                                ],
                            }
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
                    "gateforge.agent_modelica_multi_round_baseline_summary_v1",
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
            self.assertEqual(payload.get("executor_attempt_histogram"), {"1": 0, "2": 0, "3_plus": 1})
            self.assertEqual(payload.get("median_executor_attempts"), 3.0)

    def test_summary_reads_executor_attempts_from_stdout_tail_payload(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cascading_structural_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"total_tasks": 1, "taskset_frozen_path": str(taskset)}, indent=2), encoding="utf-8")
            baseline_summary = root / "baseline_summary.json"
            baseline_summary.write_text(json.dumps({"status": "PASS", "success_count": 1, "success_at_k_pct": 100.0, "median_repair_rounds": 1.0}, indent=2), encoding="utf-8")
            stdout_payload = json.dumps({"attempts": [{"round": 1}, {"round": 2}]})
            results = root / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "a",
                                "passed": True,
                                "rounds_used": 1,
                                "attempts": [{"round": 1, "executor_stdout_tail": stdout_payload}],
                            }
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
                    "gateforge.agent_modelica_multi_round_baseline_summary_v1",
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
            self.assertEqual(payload.get("executor_attempt_histogram"), {"1": 0, "2": 1, "3_plus": 0})
            self.assertEqual(payload.get("median_executor_attempts"), 2.0)


if __name__ == "__main__":
    unittest.main()
