import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaBehavioralContractEvidenceV1Tests(unittest.TestCase):
    def test_behavioral_headroom_present_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "steady_state_target_violation", "contract_family": "steady_state"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_failure_type": {"steady_state_target_violation": 1}, "counts_by_contract_family": {"steady_state": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"contract_pass_pct": 50.0, "contract_fail_by_failure_type": {"steady_state_target_violation": {"task_count": 1, "contract_fail_count": 1}}},
                "baseline_results.json": {"records": [{"task_id": "a", "contract_pass": False}]},
                "det_summary.json": {"contract_pass_pct": 50.0},
                "det_results.json": {"records": [{"task_id": "a", "contract_pass": False}]},
                "ret_summary.json": {"contract_pass_pct": 50.0},
                "ret_results.json": {"records": [{"task_id": "a", "contract_pass": False}]},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_behavioral_contract_evidence_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(root / "baseline_summary.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--deterministic-summary",
                    str(root / "det_summary.json"),
                    "--deterministic-results",
                    str(root / "det_results.json"),
                    "--retrieval-summary",
                    str(root / "ret_summary.json"),
                    "--retrieval-results",
                    str(root / "ret_results.json"),
                    "--out",
                    str(out),
                    "--gate-out",
                    str(gate),
                    "--decision-out",
                    str(decision),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "needs_review")
            self.assertEqual(payload.get("primary_reason"), "behavioral_headroom_present")

    def test_deterministic_uplift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "transient_response_contract_violation", "contract_family": "transient_response"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_failure_type": {"transient_response_contract_violation": 1}, "counts_by_contract_family": {"transient_response": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"contract_pass_pct": 66.67, "contract_fail_by_failure_type": {"transient_response_contract_violation": {"task_count": 1, "contract_fail_count": 1}}},
                "baseline_results.json": {"records": [{"task_id": "a", "contract_pass": False}]},
                "det_summary.json": {"contract_pass_pct": 100.0},
                "det_results.json": {"records": [{"task_id": "a", "contract_pass": True, "attempts": [{"attempts": [{}, {}]}]}]},
                "ret_summary.json": {"contract_pass_pct": 100.0},
                "ret_results.json": {"records": [{"task_id": "a", "contract_pass": True, "attempts": [{"attempts": [{}, {}]}]}]},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_behavioral_contract_evidence_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(root / "baseline_summary.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--deterministic-summary",
                    str(root / "det_summary.json"),
                    "--deterministic-results",
                    str(root / "det_results.json"),
                    "--retrieval-summary",
                    str(root / "ret_summary.json"),
                    "--retrieval-results",
                    str(root / "ret_results.json"),
                    "--out",
                    str(out),
                    "--gate-out",
                    str(gate),
                    "--decision-out",
                    str(decision),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "promote")
            self.assertEqual(payload.get("primary_reason"), "retrieval_hold_the_floor")
            self.assertEqual(payload.get("deterministic_uplift_status"), "observed")

    def test_behavioral_task_construction_too_easy_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "mode_transition_contract_violation", "contract_family": "mode_transition"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_failure_type": {"mode_transition_contract_violation": 1}, "counts_by_contract_family": {"mode_transition": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"contract_pass_pct": 100.0, "contract_fail_by_failure_type": {"mode_transition_contract_violation": {"task_count": 1, "contract_fail_count": 0}}},
                "baseline_results.json": {"records": [{"task_id": "a", "contract_pass": True}]},
                "det_summary.json": {"contract_pass_pct": 100.0},
                "det_results.json": {"records": [{"task_id": "a", "contract_pass": True}]},
                "ret_summary.json": {"contract_pass_pct": 100.0},
                "ret_results.json": {"records": [{"task_id": "a", "contract_pass": True}]},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_behavioral_contract_evidence_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(root / "baseline_summary.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--deterministic-summary",
                    str(root / "det_summary.json"),
                    "--deterministic-results",
                    str(root / "det_results.json"),
                    "--retrieval-summary",
                    str(root / "ret_summary.json"),
                    "--retrieval-results",
                    str(root / "ret_results.json"),
                    "--out",
                    str(out),
                    "--gate-out",
                    str(gate),
                    "--decision-out",
                    str(decision),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "hold")
            self.assertEqual(payload.get("primary_reason"), "behavioral_task_construction_too_easy")

    def test_evidence_reads_contract_pass_from_hard_checks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "steady_state_target_violation", "contract_family": "steady_state"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_failure_type": {"steady_state_target_violation": 1}, "counts_by_contract_family": {"steady_state": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"contract_pass_pct": 0.0, "contract_fail_by_failure_type": {"steady_state_target_violation": {"task_count": 1, "contract_fail_count": 1}}},
                "baseline_results.json": {"records": [{"task_id": "a", "hard_checks": {"physics_contract_pass": False}}]},
                "det_summary.json": {"contract_pass_pct": 100.0},
                "det_results.json": {"records": [{"task_id": "a", "hard_checks": {"physics_contract_pass": True}, "attempts": [{"attempts": [{}]}]}]},
                "ret_summary.json": {"contract_pass_pct": 100.0},
                "ret_results.json": {"records": [{"task_id": "a", "hard_checks": {"physics_contract_pass": True}, "attempts": [{"attempts": [{}]}]}]},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_behavioral_contract_evidence_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(root / "baseline_summary.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--deterministic-summary",
                    str(root / "det_summary.json"),
                    "--deterministic-results",
                    str(root / "det_results.json"),
                    "--retrieval-summary",
                    str(root / "ret_summary.json"),
                    "--retrieval-results",
                    str(root / "ret_results.json"),
                    "--out",
                    str(out),
                    "--gate-out",
                    str(gate),
                    "--decision-out",
                    str(decision),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("deterministic_uplift_status"), "observed")


if __name__ == "__main__":
    unittest.main()
