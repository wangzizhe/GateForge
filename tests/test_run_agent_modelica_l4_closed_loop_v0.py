import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


def _live_cmd_with_l4_switch() -> str:
    code = """
import json
l4_enabled = "__L4_ENABLED__" == "1"
payload = {
  "check_model_pass": bool(l4_enabled),
  "simulate_pass": bool(l4_enabled),
  "physics_contract_pass": bool(l4_enabled),
  "regression_pass": bool(l4_enabled),
  "elapsed_sec": 0.2,
  "error_message": "" if l4_enabled else "model check failed",
  "compile_error": "" if l4_enabled else "model check failed",
  "simulate_error_message": "",
  "attempts": [
    {
      "observed_failure_type": "none" if l4_enabled else "model_check_error",
      "reason": "" if l4_enabled else "compile/syntax error",
      "diagnostic_ir": {
        "error_type": "none" if l4_enabled else "model_check_error",
        "error_subtype": "none" if l4_enabled else "parse_lexer_error",
        "stage": "none" if l4_enabled else "check",
        "confidence": 0.9
      }
    }
  ]
}
print(json.dumps(payload))
""".strip()
    return f"python3 -c {shlex.quote(code)}"


def _live_cmd_no_delta() -> str:
    code = """
import json
payload = {
  "check_model_pass": True,
  "simulate_pass": True,
  "physics_contract_pass": True,
  "regression_pass": True,
  "elapsed_sec": 0.2,
  "attempts": [
    {
      "observed_failure_type": "none",
      "reason": "",
      "diagnostic_ir": {
        "error_type": "none",
        "error_subtype": "none",
        "stage": "none",
        "confidence": 0.9
      }
    }
  ]
}
print(json.dumps(payload))
""".strip()
    return f"python3 -c {shlex.quote(code)}"


class RunAgentModelicaL4ClosedLoopV0Tests(unittest.TestCase):
    def test_script_passes_when_l4_improves_success(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_closed_loop_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            model_path = root / "A1.mo"
            model_path.write_text(
                "\n".join(
                    [
                        "model A1",
                        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
                        "  Modelica.Electrical.Analog.Basic.Ground G1;",
                        "equation",
                        "  connect(R1.n, G1.p);",
                        "end A1;",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_small",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "expected_stage": "check",
                                "source_model_path": str(model_path),
                                "mutated_model_path": str(model_path),
                            },
                            {
                                "task_id": "t_medium",
                                "scale": "medium",
                                "failure_type": "model_check_error",
                                "expected_stage": "check",
                                "source_model_path": str(model_path),
                                "mutated_model_path": str(model_path),
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_EXECUTOR_CMD": _live_cmd_with_l4_switch(),
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_MAX_ROUNDS": "2",
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_TIMEOUT_SEC": "20",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "ab_compare_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(float((summary.get("delta") or {}).get("success_at_k_pp") or 0.0), 5.0)

    def test_script_fails_when_success_delta_below_threshold(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_closed_loop_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_fail"
            model_path = root / "A1.mo"
            model_path.write_text(
                "\n".join(
                    [
                        "model A1",
                        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
                        "  Modelica.Electrical.Analog.Basic.Ground G1;",
                        "equation",
                        "  connect(R1.n, G1.p);",
                        "end A1;",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_small",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "source_model_path": str(model_path),
                                "mutated_model_path": str(model_path),
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_EXECUTOR_CMD": _live_cmd_no_delta(),
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_TIMEOUT_SEC": "20",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=180,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "ab_compare_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            reasons = set(summary.get("reasons") or [])
            self.assertIn("success_delta_below_threshold", reasons)


if __name__ == "__main__":
    unittest.main()
