import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


def _live_cmd_for_payload(payload: dict) -> str:
    code = f"import json; payload = {repr(payload)}; print(json.dumps(payload))"
    return f"python3 -c {shlex.quote(code)}"


class RunAgentModelicaL3StabilityRegressionV0Tests(unittest.TestCase):
    def test_script_passes_with_consistent_diagnostics(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l3_stability_regression_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_small",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "expected_stage": "check",
                            },
                            {
                                "task_id": "t_medium",
                                "scale": "medium",
                                "failure_type": "model_check_error",
                                "expected_stage": "check",
                            },
                            {
                                "task_id": "t_large",
                                "scale": "large",
                                "failure_type": "simulate_error",
                                "expected_stage": "simulate",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "elapsed_sec": 0.1,
                "attempts": [
                    {
                        "observed_failure_type": "model_check_error",
                        "reason": "compile/syntax error",
                        "diagnostic_ir": {
                            "error_type": "model_check_error",
                            "error_subtype": "parse_lexer_error",
                            "stage": "check",
                            "confidence": 0.95,
                        },
                    }
                ],
            }
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L3_STABILITY_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L3_STABILITY_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L3_STABILITY_LIVE_EXECUTOR_CMD": _live_cmd_for_payload(payload),
                "GATEFORGE_AGENT_L3_STABILITY_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L3_STABILITY_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L3_STABILITY_LIVE_TIMEOUT_SEC": "20",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("filtered_task_count") or 0), 2)
            run1 = summary.get("run1") if isinstance(summary.get("run1"), dict) else {}
            run2 = summary.get("run2") if isinstance(summary.get("run2"), dict) else {}
            self.assertEqual(run1.get("l3_gate_status"), "PASS")
            self.assertEqual(run2.get("l3_gate_status"), "PASS")
            self.assertEqual(float(run1.get("l3_parse_coverage_pct") or 0.0), 100.0)
            self.assertEqual(float(run2.get("l3_parse_coverage_pct") or 0.0), 100.0)

    def test_script_fails_when_l3_gate_below_threshold(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l3_stability_regression_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_fail_gate"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "expected_stage": "simulate",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "elapsed_sec": 0.1,
                "attempts": [
                    {
                        "observed_failure_type": "simulate_error",
                        "reason": "simulation failed",
                        "diagnostic_ir": {
                            "error_type": "model_check_error",
                            "error_subtype": "parse_lexer_error",
                            "stage": "check",
                            "confidence": 0.95,
                        },
                    }
                ],
            }
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L3_STABILITY_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L3_STABILITY_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L3_STABILITY_LIVE_EXECUTOR_CMD": _live_cmd_for_payload(payload),
                "GATEFORGE_AGENT_L3_STABILITY_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L3_STABILITY_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L3_STABILITY_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L3_MIN_TYPE_MATCH_RATE_PCT": "90",
                "GATEFORGE_AGENT_L3_MIN_STAGE_MATCH_RATE_PCT": "90",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=120,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            reasons = set(summary.get("reasons") or [])
            self.assertIn("run1_l3_gate_not_pass", reasons)
            self.assertIn("run2_l3_gate_not_pass", reasons)

    def test_script_fails_on_infra_reason(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l3_stability_regression_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_fail_infra"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "expected_stage": "check",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "elapsed_sec": 0.1,
                "attempts": [
                    {
                        "observed_failure_type": "model_check_error",
                        "reason": "permission denied while trying to connect to the docker API",
                        "diagnostic_ir": {
                            "error_type": "model_check_error",
                            "error_subtype": "compile_failure_unknown",
                            "stage": "check",
                            "confidence": 0.95,
                        },
                    }
                ],
            }
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L3_STABILITY_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L3_STABILITY_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L3_STABILITY_LIVE_EXECUTOR_CMD": _live_cmd_for_payload(payload),
                "GATEFORGE_AGENT_L3_STABILITY_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L3_STABILITY_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L3_STABILITY_LIVE_TIMEOUT_SEC": "20",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=120,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            reasons = set(summary.get("reasons") or [])
            self.assertIn("run1_infra_failure_present", reasons)
            self.assertIn("run2_infra_failure_present", reasons)
            run1 = summary.get("run1") if isinstance(summary.get("run1"), dict) else {}
            infra_by_reason = run1.get("infra_failure_by_reason") if isinstance(run1.get("infra_failure_by_reason"), dict) else {}
            self.assertGreaterEqual(int(infra_by_reason.get("docker_permission_denied") or 0), 1)


if __name__ == "__main__":
    unittest.main()
