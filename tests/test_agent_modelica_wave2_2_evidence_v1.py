import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaWave22EvidenceV1Tests(unittest.TestCase):
    def test_baseline_saturation_becomes_task_too_easy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = root / "challenge.json"
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cross_component_parameter_coupling_error", "coupling_span": "cross_component"}]}, indent=2), encoding="utf-8")
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"liba": 1}, "counts_by_failure_type": {"cross_component_parameter_coupling_error": 1}, "counts_by_coupling_span": {"cross_component": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 100.0, "trivial_restore_suspected_pct": 100.0, "first_round_pass_pct": 100.0},
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
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_wave2_2_evidence_v1",
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
                    "--retrieval-audit-summary",
                    str(root / "audit.json"),
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
            self.assertEqual(payload.get("primary_reason"), "task_construction_still_too_easy")
            self.assertEqual(payload.get("retrieval_uplift_status"), "task_construction_still_too_easy")

    def test_saturated_but_not_too_easy_becomes_baseline_saturated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = root / "challenge.json"
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cross_component_parameter_coupling_error", "coupling_span": "cross_component"}]}, indent=2), encoding="utf-8")
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"liba": 1}, "counts_by_failure_type": {"cross_component_parameter_coupling_error": 1}, "counts_by_coupling_span": {"cross_component": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 100.0, "trivial_restore_suspected_pct": 0.0, "first_round_pass_pct": 0.0},
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
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_wave2_2_evidence_v1",
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
                    "--retrieval-audit-summary",
                    str(root / "audit.json"),
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
            self.assertEqual(payload.get("primary_reason"), "baseline_already_saturated")
            self.assertEqual(payload.get("retrieval_uplift_status"), "baseline_already_saturated")

    def test_headroom_remaining_is_reported_before_uplift(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = root / "challenge.json"
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "a", "failure_type": "cross_component_parameter_coupling_error", "coupling_span": "cross_component"}]}, indent=2), encoding="utf-8")
            challenge.write_text(json.dumps({"taskset_frozen_path": str(taskset), "counts_by_library": {"liba": 1}, "counts_by_failure_type": {"cross_component_parameter_coupling_error": 1}, "counts_by_coupling_span": {"cross_component": 1}}, indent=2), encoding="utf-8")
            for name, payload in {
                "baseline_summary.json": {"success_at_k_pct": 66.67, "trivial_restore_suspected_pct": 0.0, "first_round_pass_pct": 33.33},
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
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_wave2_2_evidence_v1",
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
                    "--retrieval-audit-summary",
                    str(root / "audit.json"),
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
            self.assertEqual(payload.get("primary_reason"), "headroom_remaining")
            self.assertEqual(payload.get("retrieval_uplift_status"), "headroom_remaining")


if __name__ == "__main__":
    unittest.main()
