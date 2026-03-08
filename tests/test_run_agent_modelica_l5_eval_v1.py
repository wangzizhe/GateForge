import json
import os
import shlex
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _cmd_pass() -> str:
    code = """
import json
payload = {
  "check_model_pass": True,
  "simulate_pass": True,
  "physics_contract_pass": True,
  "regression_pass": True,
  "elapsed_sec": 0.1,
  "attempts": [
    {
      "observed_failure_type": "model_check_error",
      "reason": "ok",
      "diagnostic_ir": {
        "error_type": "model_check_error",
        "error_subtype": "parse_lexer_error",
        "stage": "check",
        "confidence": 0.95
      }
    }
  ]
}
print(json.dumps(payload))
""".strip()
    return f"python3 -c {shlex.quote(code)}"


def _cmd_l4_switch() -> str:
    code = """
import json
l4_enabled = "__L4_ENABLED__" == "1"
payload = {
  "check_model_pass": bool(l4_enabled),
  "simulate_pass": bool(l4_enabled),
  "physics_contract_pass": bool(l4_enabled),
  "regression_pass": bool(l4_enabled),
  "elapsed_sec": 0.1,
  "error_message": "" if l4_enabled else "model check failed",
  "compile_error": "" if l4_enabled else "model check failed",
  "attempts": [
    {
      "observed_failure_type": "none" if l4_enabled else "model_check_error",
      "reason": "ok" if l4_enabled else "compile/syntax error",
      "diagnostic_ir": {
        "error_type": "none" if l4_enabled else "model_check_error",
        "error_subtype": "none" if l4_enabled else "parse_lexer_error",
        "stage": "none" if l4_enabled else "check",
        "confidence": 0.95
      }
    }
  ]
}
print(json.dumps(payload))
""".strip()
    return f"python3 -c {shlex.quote(code)}"


def _cmd_l4_switch_with_infra() -> str:
    code = """
import json
l4_enabled = "__L4_ENABLED__" == "1"
payload = {
  "check_model_pass": bool(l4_enabled),
  "simulate_pass": bool(l4_enabled),
  "physics_contract_pass": bool(l4_enabled),
  "regression_pass": bool(l4_enabled),
  "elapsed_sec": 0.1,
  "error_message": "" if l4_enabled else "model check failed",
  "compile_error": "" if l4_enabled else "model check failed",
  "attempts": [
    {
      "observed_failure_type": "none" if l4_enabled else "model_check_error",
      "reason": "permission denied while trying to connect to the docker API" if l4_enabled else "compile/syntax error",
      "diagnostic_ir": {
        "error_type": "none" if l4_enabled else "model_check_error",
        "error_subtype": "none" if l4_enabled else "parse_lexer_error",
        "stage": "none" if l4_enabled else "check",
        "confidence": 0.95
      }
    }
  ]
}
print(json.dumps(payload))
""".strip()
    return f"python3 -c {shlex.quote(code)}"


class RunAgentModelicaL5EvalV1ScriptTests(unittest.TestCase):
    def test_script_passes_with_positive_delta_and_clean_infra(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l5_eval_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t_small", "scale": "small", "failure_type": "model_check_error", "expected_stage": "check"},
                            {"task_id": "t_medium", "scale": "medium", "failure_type": "simulate_error", "expected_stage": "simulate"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L5_EVAL_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L5_EVAL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=240,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "l5_eval_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(float(summary.get("delta_success_at_k_pp") or 0.0), 5.0)
            self.assertEqual(int(summary.get("infra_failure_count", -1)), 0)

    def test_script_fails_when_delta_below_threshold(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l5_eval_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_fail_delta"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t_small", "scale": "small", "failure_type": "model_check_error", "expected_stage": "check"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L5_EVAL_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L5_EVAL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD": _cmd_pass(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=240,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "l5_eval_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("delta_success_at_k_below_threshold", set(summary.get("reasons") or []))

    def test_script_fails_when_infra_reason_detected(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l5_eval_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_fail_infra"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t_small", "scale": "small", "failure_type": "model_check_error", "expected_stage": "check"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L5_EVAL_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L5_EVAL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch_with_infra(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=240,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "l5_eval_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("infra_failure_count_not_zero", set(summary.get("reasons") or []))

    def test_weekly_recommendation_requires_two_week_consecutive_pass(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l5_eval_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_weekly_promote"
            ledger = root / "private" / "ledger.jsonl"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t_small", "scale": "small", "failure_type": "model_check_error", "expected_stage": "check"},
                            {"task_id": "t_medium", "scale": "medium", "failure_type": "simulate_error", "expected_stage": "simulate"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            previous_week = datetime.now(timezone.utc) - timedelta(days=8)
            previous_row = {
                "generated_at_utc": previous_week.isoformat(),
                "l5_gate_status": "PASS",
                "status": "PASS",
                "gate_result": "PASS",
                "delta_success_at_k_pp": 6.0,
                "infra_failure_count": 0,
                "primary_reason": "none",
                "reason_enum": ["reason_enum_unknown"],
            }
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text(json.dumps(previous_row) + "\n", encoding="utf-8")

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L5_EVAL_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L5_EVAL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L5_LEDGER_PATH": str(ledger),
                "GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=240,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            weekly = json.loads((out_dir / "l5_weekly_metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(str(weekly.get("recommendation") or ""), "promote")
            self.assertEqual(str(weekly.get("recommendation_reason") or ""), "two_week_consecutive_pass")

    def test_weekly_recommendation_holds_without_previous_week(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l5_eval_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_weekly_hold"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t_small", "scale": "small", "failure_type": "model_check_error", "expected_stage": "check"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L5_EVAL_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L5_EVAL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=240,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            weekly = json.loads((out_dir / "l5_weekly_metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(str(weekly.get("recommendation") or ""), "hold")
            self.assertEqual(str(weekly.get("recommendation_reason") or ""), "insufficient_consecutive_history")


if __name__ == "__main__":
    unittest.main()
