import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


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


def _cmd_always_fail() -> str:
    code = """
import json
payload = {
  "check_model_pass": False,
  "simulate_pass": False,
  "physics_contract_pass": False,
  "regression_pass": False,
  "elapsed_sec": 0.1,
  "error_message": "model check failed",
  "compile_error": "model check failed",
  "attempts": [
    {
      "observed_failure_type": "model_check_error",
      "reason": "compile/syntax error",
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


class RunAgentModelicaL4ProfileSweepV0ScriptTests(unittest.TestCase):
    def test_profile_sweep_selects_best_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_profile_sweep_v0.sh"
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
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_SCALES": "small,medium",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_PROFILES": "score_v1,score_v1a",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=360,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertIn(str(summary.get("recommended_profile") or ""), {"score_v1", "score_v1a"})
            rows = summary.get("profile_results") if isinstance(summary.get("profile_results"), list) else []
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(str(x.get("status") or "") == "PASS" for x in rows if isinstance(x, dict)))

    def test_profile_sweep_enforce_pass_fails_when_no_profile_passes(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_profile_sweep_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_fail"
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
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_SCALES": "small,medium",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_PROFILES": "score_v1,score_v1a",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_EXECUTOR_CMD": _cmd_always_fail(),
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_ENFORCE_PASS": "1",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=360,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertEqual(str(summary.get("recommended_profile") or ""), "")


if __name__ == "__main__":
    unittest.main()
