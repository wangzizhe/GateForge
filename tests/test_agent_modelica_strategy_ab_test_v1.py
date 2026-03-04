import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaStrategyABTestV1Tests(unittest.TestCase):
    def test_ab_test_outputs_decision_and_delta(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            playbook = root / "playbook.json"
            out = root / "ab_summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "scale": "small", "failure_type": "simulate_error", "expected_stage": "simulate"},
                            {"task_id": "t2", "scale": "medium", "failure_type": "semantic_regression", "expected_stage": "simulate"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            playbook.write_text(
                json.dumps(
                    {
                        "playbook": [
                            {
                                "failure_type": "simulate_error",
                                "strategy_id": "sim_init_stability",
                                "name": "sim",
                                "priority": 100,
                                "actions": ["a"],
                                "preferred_stage": "simulate",
                            },
                            {
                                "failure_type": "semantic_regression",
                                "strategy_id": "sem_invariant_first",
                                "name": "sem",
                                "priority": 100,
                                "actions": ["a"],
                                "preferred_stage": "simulate",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_strategy_ab_test_v1",
                    "--taskset",
                    str(taskset),
                    "--treatment-playbook",
                    str(playbook),
                    "--out-dir",
                    str(root / "out"),
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
            self.assertIn(payload.get("decision"), {"PROMOTE_TREATMENT", "KEEP_CONTROL"})
            self.assertIn("delta", payload)
            self.assertIn("strategy_signal", payload)
            self.assertIn("strategy_signal_by_failure_type", payload)
            self.assertIn("decision_breakdown", payload)

    def test_evidence_mode_uses_strategy_signal_tiebreak(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            playbook = root / "playbook.json"
            out = root / "ab_summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "e1",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "observed_elapsed_sec": 40,
                                "observed_repair_rounds": 2,
                                "baseline_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                                "candidate_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                            },
                            {
                                "task_id": "e2",
                                "scale": "medium",
                                "failure_type": "model_check_error",
                                "expected_stage": "check_model",
                                "observed_elapsed_sec": 40,
                                "observed_repair_rounds": 2,
                                "baseline_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                                "candidate_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            playbook.write_text(
                json.dumps(
                    {
                        "playbook": [
                            {
                                "failure_type": "simulate_error",
                                "strategy_id": "sim_stage",
                                "name": "sim",
                                "priority": 100,
                                "actions": ["a"],
                                "preferred_stage": "simulate",
                            },
                            {
                                "failure_type": "model_check_error",
                                "strategy_id": "mc_stage",
                                "name": "mc",
                                "priority": 100,
                                "actions": ["a"],
                                "preferred_stage": "check_model",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_strategy_ab_test_v1",
                    "--taskset",
                    str(taskset),
                    "--treatment-playbook",
                    str(playbook),
                    "--mode",
                    "evidence",
                    "--evidence-signal-threshold",
                    "0.05",
                    "--out-dir",
                    str(root / "out"),
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
            self.assertEqual(payload.get("decision"), "PROMOTE_TREATMENT")
            signal = payload.get("strategy_signal", {})
            self.assertTrue(bool(signal.get("triggered")))
            self.assertGreater(float(signal.get("delta_score", 0.0)), 0.0)
            breakdown = payload.get("decision_breakdown", {})
            self.assertTrue(bool(breakdown.get("core_tie")))
            self.assertFalse(bool(breakdown.get("core_improvement")))


if __name__ == "__main__":
    unittest.main()
