import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


def _budget_sensitive_cmd() -> str:
    code = """
import json
import sys

max_rounds = int(sys.argv[1])
task_id = str(sys.argv[2])
passing = {"s1", "m1"} if max_rounds <= 1 else {"s1", "m1", "s2", "m2"}
ok = task_id in passing
payload = {
  "check_model_pass": ok,
  "simulate_pass": ok,
  "physics_contract_pass": ok,
  "regression_pass": ok,
  "elapsed_sec": 0.1,
  "error_message": "" if ok else "mock_failure",
  "compile_error": "" if ok else "mock_failure",
  "simulate_error_message": "" if ok else "mock_failure",
  "stderr_snippet": "" if ok else "mock_failure",
  "attempts": [
    {
      "observed_failure_type": "none" if ok else "model_check_error",
      "reason": "" if ok else "mock_failure",
      "stderr_snippet": "" if ok else "mock_failure",
      "repair_actions_planned": ["mock_action"],
      "diagnostic_ir": {
        "error_type": "none" if ok else "model_check_error",
        "error_subtype": "none" if ok else "mock_failure",
        "stage": "none" if ok else "check",
        "confidence": 0.95
      }
    }
  ]
}
print(json.dumps(payload))
""".strip()
    return f"python3 -c {shlex.quote(code)} __MAX_ROUNDS__ __TASK_ID__"


def _taskset_payload(model_path: str) -> dict:
    rows = []
    for i, failure_type in enumerate(["model_check_error", "simulate_error", "semantic_regression"], start=1):
        rows.append(
            {
                "task_id": f"s{i}",
                "scale": "small",
                "failure_type": failure_type,
                "expected_stage": "check" if failure_type != "simulate_error" else "simulate",
                "source_model_path": model_path,
                "mutated_model_path": model_path,
            }
        )
        rows.append(
            {
                "task_id": f"m{i}",
                "scale": "medium",
                "failure_type": failure_type,
                "expected_stage": "check" if failure_type != "simulate_error" else "simulate",
                "source_model_path": model_path,
                "mutated_model_path": model_path,
            }
        )
    return {"tasks": rows}


class RunAgentModelicaL4CanonicalBaselineV0ScriptTests(unittest.TestCase):
    def test_script_selects_first_stable_in_range_budget(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_canonical_baseline_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A1.mo"
            model.write_text("model A1\nend A1;\n", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps(_taskset_payload(str(model))), encoding="utf-8")
            out_dir = root / "baseline"

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_BUDGETS": "1x20,2x20,2x30",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_REPEAT_COUNT": "2",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_TARGET_MIN_OFF_SUCCESS_PCT": "60",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_TARGET_MAX_OFF_SUCCESS_PCT": "90",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_REQUIRED_TOTAL_RUNS": "3",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_MIN_IN_RANGE_RUNS": "2",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_MAX_REPEAT_SPREAD_PP": "20",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_REUSE_EXISTING": "0",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_LIVE_EXECUTOR_CMD": _budget_sensitive_cmd(),
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_CANONICAL_BASELINE_RUNTIME_THRESHOLD": "0.2",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((out_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("decision") or ""), "ready")
            self.assertEqual(str(summary.get("primary_reason") or ""), "none")
            canonical = summary.get("canonical_budget") if isinstance(summary.get("canonical_budget"), dict) else {}
            self.assertEqual(str(canonical.get("budget_token") or ""), "2x20")
            self.assertEqual(str(manifest.get("selected_budget") or ""), "2x20")
            self.assertEqual(int(summary.get("stability_total_run_count") or 0), 3)


if __name__ == "__main__":
    unittest.main()
