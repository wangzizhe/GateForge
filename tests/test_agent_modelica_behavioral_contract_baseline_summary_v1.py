import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaBehavioralContractBaselineSummaryV1Tests(unittest.TestCase):
    def test_summary_emits_contract_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "a", "failure_type": "steady_state_target_violation", "contract_family": "steady_state"},
                            {"task_id": "b", "failure_type": "transient_response_contract_violation", "contract_family": "transient_response"},
                            {"task_id": "c", "failure_type": "mode_transition_contract_violation", "contract_family": "mode_transition"},
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
                        "total_tasks": 3,
                        "counts_by_failure_type": {
                            "steady_state_target_violation": 1,
                            "transient_response_contract_violation": 1,
                            "mode_transition_contract_violation": 1,
                        },
                        "counts_by_contract_family": {"steady_state": 1, "transient_response": 1, "mode_transition": 1},
                        "taskset_frozen_path": str(taskset),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            baseline_summary = root / "baseline_summary.json"
            baseline_summary.write_text(json.dumps({"status": "PASS", "success_count": 1, "success_at_k_pct": 33.33}, indent=2), encoding="utf-8")
            results = root / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "a", "passed": False, "contract_pass": False, "contract_fail_bucket": "steady_state_miss", "attempts": [{"round": 1}, {"round": 2}]},
                            {"task_id": "b", "passed": False, "contract_pass": False, "contract_fail_bucket": "overshoot_or_settling_violation", "attempts": [{"round": 1}, {"round": 2}, {"round": 3}]},
                            {"task_id": "c", "passed": True, "contract_pass": True, "attempts": [{"round": 1}]},
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
                    "gateforge.agent_modelica_behavioral_contract_baseline_summary_v1",
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
            self.assertEqual(payload.get("contract_pass_pct"), 33.33)
            self.assertEqual(payload.get("contract_fail_breakdown", {}).get("steady_state_miss"), 1)
            self.assertEqual(payload.get("contract_fail_breakdown", {}).get("overshoot_or_settling_violation"), 1)
            self.assertEqual(payload.get("median_executor_attempts"), 2.0)
            self.assertEqual(payload.get("contract_headroom_status"), "behavioral_headroom_present")

    def test_summary_reads_contract_pass_from_hard_checks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps({"tasks": [{"task_id": "a", "failure_type": "steady_state_target_violation", "contract_family": "steady_state"}]}, indent=2),
                encoding="utf-8",
            )
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"total_tasks": 1, "taskset_frozen_path": str(taskset)}, indent=2), encoding="utf-8")
            baseline_summary = root / "baseline_summary.json"
            baseline_summary.write_text(json.dumps({"status": "PASS", "success_count": 0, "success_at_k_pct": 0.0}, indent=2), encoding="utf-8")
            results = root / "results.json"
            results.write_text(
                json.dumps({"records": [{"task_id": "a", "passed": False, "hard_checks": {"physics_contract_pass": True}, "attempts": [{"round": 1}]}]}, indent=2),
                encoding="utf-8",
            )
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_behavioral_contract_baseline_summary_v1",
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
            self.assertEqual(payload.get("contract_pass_pct"), 100.0)


if __name__ == "__main__":
    unittest.main()
