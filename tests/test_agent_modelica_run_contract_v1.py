import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaRunContractV1Tests(unittest.TestCase):
    def test_run_contract_mock_produces_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "scale": "small", "failure_type": "model_check_error"},
                            {"task_id": "t2", "scale": "medium", "failure_type": "simulate_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--max-rounds",
                    "5",
                    "--max-time-sec",
                    "300",
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertIn(s.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(s.get("total_tasks", 0)), 2)
            self.assertEqual(len(r.get("records", [])), 2)
            self.assertIsNotNone(s.get("median_repair_rounds"))
            self.assertIn("repair_strategy", r["records"][0])
            self.assertTrue(str((r["records"][0].get("repair_strategy") or {}).get("strategy_id") or ""))

    def test_run_contract_applies_physics_contract_v0_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_physics_fail",
                                "scale": "small",
                                "failure_type": "semantic_regression",
                                "mock_success_round": 1,
                                "mock_round_duration_sec": 5,
                                "baseline_metrics": {"steady_state_error": 0.01},
                                "candidate_metrics": {"steady_state_error": 0.2},
                                "physical_invariants": [
                                    {
                                        "type": "range",
                                        "metric": "steady_state_error",
                                        "min": 0.0,
                                        "max": 0.05,
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--max-rounds",
                    "3",
                    "--max-time-sec",
                    "60",
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(int(s.get("success_count", 0)), 0)
            self.assertEqual(int(s.get("physics_fail_count", 0)), 1)
            self.assertEqual(r.get("physics_contract_schema_version"), "physics_contract_v0")
            self.assertFalse(bool(r["records"][0]["hard_checks"]["physics_contract_pass"]))
            reasons = r["records"][0].get("physics_contract_reasons") or []
            self.assertTrue(any(str(x).startswith("physical_invariant_") for x in reasons))
            self.assertEqual((r["records"][0].get("repair_strategy") or {}).get("strategy_id"), "sem_invariant_first")

    def test_run_contract_evidence_mode_uses_real_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            results = root / "results.json"
            summary = root / "summary.json"
            baseline.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "gate": "PASS",
                        "check_ok": True,
                        "simulate_ok": True,
                        "metrics": {
                            "steady_state_error": 0.01,
                            "overshoot": 0.04,
                            "settling_time": 1.2,
                            "runtime_seconds": 2.0,
                            "events": 12,
                        },
                    }
                ),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "gate": "PASS",
                        "check_ok": True,
                        "simulate_ok": True,
                        "metrics": {
                            "steady_state_error": 0.02,
                            "overshoot": 0.05,
                            "settling_time": 1.5,
                            "runtime_seconds": 2.3,
                            "events": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_evidence",
                                "scale": "medium",
                                "failure_type": "semantic_regression",
                                "baseline_evidence_path": str(baseline),
                                "candidate_evidence_path": str(candidate),
                                "observed_repair_rounds": 2,
                                "observed_elapsed_sec": 40,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "evidence",
                    "--max-rounds",
                    "5",
                    "--max-time-sec",
                    "300",
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(s.get("mode"), "evidence")
            self.assertEqual(int(s.get("success_count", 0)), 1)
            self.assertEqual(int(s.get("physics_fail_count", 0)), 0)
            self.assertTrue(bool(r["records"][0]["hard_checks"]["regression_pass"]))
            self.assertEqual((r["records"][0].get("repair_strategy") or {}).get("strategy_id"), "sem_invariant_first")

    def test_run_contract_augments_strategy_with_templates_error_map_and_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            history = root / "history.json"
            results = root / "results.json"
            summary = root / "summary.json"
            history.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "failure_type": "model_check_error",
                                "model_id": "LargeGrid",
                                "used_strategy": "mc_undefined_symbol_guard",
                                "action_trace": ["declare missing symbol and align declaration scope"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_aug",
                                "scale": "large",
                                "failure_type": "model_check_error",
                                "source_model_path": "LargeGrid.mo",
                                "error_message": "Error: undefined symbol X",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--repair-history",
                    str(history),
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            r = json.loads(results.read_text(encoding="utf-8"))
            rec = (r.get("records") or [])[0]
            audit = rec.get("repair_audit") or {}
            self.assertTrue(str(audit.get("patch_template_id") or "").startswith("tpl_"))
            self.assertGreaterEqual(int(audit.get("error_action_count", 0)), 1)
            self.assertGreaterEqual(int(audit.get("retrieved_example_count", 0)), 1)
            actions = audit.get("actions_planned") if isinstance(audit.get("actions_planned"), list) else []
            self.assertTrue(any("declare missing symbol" in str(x).lower() for x in actions))

    def test_run_contract_focus_queue_reduces_stress_runtime_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            focus_queue = root / "focus_queue.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_focus_reg",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "_stress_class": "slow_pass",
                                "_stress_reason": "slow_pass_runtime_stress",
                                "observed_repair_rounds": 2,
                                "observed_elapsed_sec": 80,
                                "baseline_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {
                                        "steady_state_error": 0.01,
                                        "overshoot": 0.04,
                                        "settling_time": 1.2,
                                        "runtime_seconds": 2.0,
                                        "events": 12,
                                    },
                                },
                                "candidate_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {
                                        "steady_state_error": 0.01,
                                        "overshoot": 0.04,
                                        "settling_time": 1.2,
                                        "runtime_seconds": 3.0,
                                        "events": 12,
                                    },
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            focus_queue.write_text(
                json.dumps(
                    {
                        "queue": [
                            {
                                "rank": 1,
                                "failure_type": "simulate_error",
                                "gate_break_reason": "regression_fail",
                                "count": 5,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "evidence",
                    "--focus-queue",
                    str(focus_queue),
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            r = json.loads(results.read_text(encoding="utf-8"))
            rec = (r.get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            self.assertTrue(bool((rec.get("hard_checks") or {}).get("regression_pass")))
            audit = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
            self.assertTrue(bool(audit.get("stress_repair_applied")))
            tags = audit.get("stress_repair_applied_tags") if isinstance(audit.get("stress_repair_applied_tags"), list) else []
            self.assertIn("repair_runtime_regression", tags)


if __name__ == "__main__":
    unittest.main()
