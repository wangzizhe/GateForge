import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaMultiRoundEvidenceV1Tests(unittest.TestCase):
    def test_easy_pack_becomes_hold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cascading_structural_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"lib": 1}, "counts_by_failure_type": {"cascading_structural_failure": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 100.0, "first_round_pass_pct": 100.0, "median_repair_rounds": 1.0},
                "baseline_results.json": {"records": [{"task_id": "a", "passed": True}]},
                "det_summary.json": {"success_at_k_pct": 100.0},
                "det_results.json": {"records": []},
                "ret_summary.json": {"success_at_k_pct": 100.0},
                "ret_results.json": {"records": []},
                "audit.json": {"retrieval_coverage_pct": 0.0, "match_signal_coverage_pct": 0.0},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_evidence_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(root / "baseline_summary.json"), "--baseline-results", str(root / "baseline_results.json"), "--deterministic-summary", str(root / "det_summary.json"), "--deterministic-results", str(root / "det_results.json"), "--retrieval-summary", str(root / "ret_summary.json"), "--retrieval-results", str(root / "ret_results.json"), "--retrieval-audit-summary", str(root / "audit.json"), "--out", str(out), "--gate-out", str(gate), "--decision-out", str(decision)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "hold")
            self.assertEqual(payload.get("primary_reason"), "task_construction_still_too_easy")

    def test_headroom_present_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cascading_structural_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"lib": 1}, "counts_by_failure_type": {"cascading_structural_failure": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 66.67, "first_round_pass_pct": 33.33, "median_repair_rounds": 2.0},
                "baseline_results.json": {"records": [{"task_id": "a", "passed": False}]},
                "det_summary.json": {"success_at_k_pct": 66.67},
                "det_results.json": {"records": []},
                "ret_summary.json": {"success_at_k_pct": 66.67},
                "ret_results.json": {"records": []},
                "audit.json": {"retrieval_coverage_pct": 0.0, "match_signal_coverage_pct": 0.0},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_evidence_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(root / "baseline_summary.json"), "--baseline-results", str(root / "baseline_results.json"), "--deterministic-summary", str(root / "det_summary.json"), "--deterministic-results", str(root / "det_results.json"), "--retrieval-summary", str(root / "ret_summary.json"), "--retrieval-results", str(root / "ret_results.json"), "--retrieval-audit-summary", str(root / "audit.json"), "--out", str(out), "--gate-out", str(gate), "--decision-out", str(decision)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "needs_review")
            self.assertEqual(payload.get("primary_reason"), "multi_round_headroom_present")

    def test_deterministic_uplift_does_not_claim_retrieval_uplift(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cascading_structural_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"lib": 1}, "counts_by_failure_type": {"cascading_structural_failure": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 88.89, "executor_first_attempt_pass_pct": 16.67, "median_executor_attempts": 2.0},
                "baseline_results.json": {"records": [{"task_id": "a", "passed": False}]},
                "det_summary.json": {"success_at_k_pct": 100.0},
                "det_results.json": {"records": [{"task_id": "a", "passed": True}]},
                "ret_summary.json": {"success_at_k_pct": 83.33},
                "ret_results.json": {"records": [{"task_id": "a", "passed": False}]},
                "audit.json": {"retrieval_coverage_pct": 100.0, "match_signal_coverage_pct": 100.0},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_evidence_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(root / "baseline_summary.json"), "--baseline-results", str(root / "baseline_results.json"), "--deterministic-summary", str(root / "det_summary.json"), "--deterministic-results", str(root / "det_results.json"), "--retrieval-summary", str(root / "ret_summary.json"), "--retrieval-results", str(root / "ret_results.json"), "--retrieval-audit-summary", str(root / "audit.json"), "--out", str(out), "--gate-out", str(gate), "--decision-out", str(decision)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "promote")
            self.assertEqual(payload.get("retrieval_uplift_status"), "not_observed")
            self.assertEqual(payload.get("deterministic_uplift_status"), "observed")

    def test_retrieval_uplift_is_reported_only_when_beating_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cascading_structural_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"lib": 1}, "counts_by_failure_type": {"cascading_structural_failure": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 88.89, "executor_first_attempt_pass_pct": 16.67, "median_executor_attempts": 2.0},
                "baseline_results.json": {"records": [{"task_id": "a", "passed": False}]},
                "det_summary.json": {"success_at_k_pct": 94.44},
                "det_results.json": {"records": [{"task_id": "a", "passed": True}]},
                "ret_summary.json": {"success_at_k_pct": 100.0},
                "ret_results.json": {"records": [{"task_id": "a", "passed": True}]},
                "audit.json": {"retrieval_coverage_pct": 100.0, "match_signal_coverage_pct": 100.0},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_evidence_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(root / "baseline_summary.json"), "--baseline-results", str(root / "baseline_results.json"), "--deterministic-summary", str(root / "det_summary.json"), "--deterministic-results", str(root / "det_results.json"), "--retrieval-summary", str(root / "ret_summary.json"), "--retrieval-results", str(root / "ret_results.json"), "--retrieval-audit-summary", str(root / "audit.json"), "--out", str(out), "--gate-out", str(gate), "--decision-out", str(decision)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "promote")
            self.assertEqual(payload.get("retrieval_uplift_status"), "retrieval_uplift_observed")
            self.assertEqual(payload.get("deterministic_uplift_status"), "observed")

    def test_retrieval_hold_the_floor_when_matching_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "coupled_conflict_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"lib": 1}, "counts_by_failure_type": {"coupled_conflict_failure": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 88.89, "executor_first_attempt_pass_pct": 16.67, "median_executor_attempts": 2.0},
                "baseline_results.json": {"records": [{"task_id": "a", "passed": False}]},
                "det_summary.json": {"success_at_k_pct": 100.0},
                "det_results.json": {"records": [{"task_id": "a", "passed": True, "time_to_pass_sec": 12.0, "attempts": [{"attempts": [{}, {}]}]}]},
                "ret_summary.json": {"success_at_k_pct": 100.0},
                "ret_results.json": {"records": [{"task_id": "a", "passed": True, "time_to_pass_sec": 12.0, "attempts": [{"attempts": [{}, {}]}]}]},
                "audit.json": {"retrieval_coverage_pct": 100.0, "match_signal_coverage_pct": 100.0},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_evidence_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(root / "baseline_summary.json"), "--baseline-results", str(root / "baseline_results.json"), "--deterministic-summary", str(root / "det_summary.json"), "--deterministic-results", str(root / "det_results.json"), "--retrieval-summary", str(root / "ret_summary.json"), "--retrieval-results", str(root / "ret_results.json"), "--retrieval-audit-summary", str(root / "audit.json"), "--out", str(out), "--gate-out", str(gate), "--decision-out", str(decision)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("retrieval_uplift_status"), "retrieval_hold_the_floor")
            self.assertEqual(payload.get("retrieval_vs_deterministic_delta_pp"), 0.0)

    def test_retrieval_uplift_observed_when_time_improves_at_equal_success(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "coupled_conflict_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"lib": 1}, "counts_by_failure_type": {"coupled_conflict_failure": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 88.89, "executor_first_attempt_pass_pct": 16.67, "median_executor_attempts": 2.0},
                "baseline_results.json": {"records": [{"task_id": "a", "passed": False}]},
                "det_summary.json": {"success_at_k_pct": 100.0},
                "det_results.json": {"records": [{"task_id": "a", "passed": True, "time_to_pass_sec": 12.0, "attempts": [{"attempts": [{}, {}]}]}]},
                "ret_summary.json": {"success_at_k_pct": 100.0},
                "ret_results.json": {"records": [{"task_id": "a", "passed": True, "time_to_pass_sec": 9.0, "attempts": [{"attempts": [{}, {}]}]}]},
                "audit.json": {"retrieval_coverage_pct": 100.0, "match_signal_coverage_pct": 100.0},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_evidence_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(root / "baseline_summary.json"), "--baseline-results", str(root / "baseline_results.json"), "--deterministic-summary", str(root / "det_summary.json"), "--deterministic-results", str(root / "det_results.json"), "--retrieval-summary", str(root / "ret_summary.json"), "--retrieval-results", str(root / "ret_results.json"), "--retrieval-audit-summary", str(root / "audit.json"), "--out", str(out), "--gate-out", str(gate), "--decision-out", str(decision)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("retrieval_uplift_status"), "retrieval_uplift_observed")
            self.assertLess(float(payload.get("retrieval_time_delta_sec") or 0.0), 0.0)

    def test_retrieval_limit_reached_when_no_family_has_incremental_gain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "coupled_conflict_failure"}]}, indent=2), encoding="utf-8")
            challenge = root / "challenge.json"
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"lib": 1}, "counts_by_failure_type": {"coupled_conflict_failure": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 88.89, "executor_first_attempt_pass_pct": 16.67, "median_executor_attempts": 2.0},
                "baseline_results.json": {"records": [{"task_id": "a", "passed": False}]},
                "det_summary.json": {"success_at_k_pct": 100.0},
                "det_results.json": {"records": [{"task_id": "a", "passed": True, "time_to_pass_sec": 10.0, "attempts": [{"attempts": [{}, {}]}]}]},
                "ret_summary.json": {"success_at_k_pct": 100.0},
                "ret_results.json": {"records": [{"task_id": "a", "passed": True, "time_to_pass_sec": 10.0, "attempts": [{"attempts": [{}, {}]}]}]},
                "audit.json": {"retrieval_coverage_pct": 100.0, "match_signal_coverage_pct": 100.0},
            }.items():
                (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.agent_modelica_multi_round_evidence_v1", "--challenge-summary", str(challenge), "--baseline-summary", str(root / "baseline_summary.json"), "--baseline-results", str(root / "baseline_results.json"), "--deterministic-summary", str(root / "det_summary.json"), "--deterministic-results", str(root / "det_results.json"), "--retrieval-summary", str(root / "ret_summary.json"), "--retrieval-results", str(root / "ret_results.json"), "--retrieval-audit-summary", str(root / "audit.json"), "--out", str(out), "--gate-out", str(gate), "--decision-out", str(decision)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("retrieval_limit_status"), "retrieval_limit_reached")


if __name__ == "__main__":
    unittest.main()
