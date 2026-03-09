import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


def _cmd_always_pass() -> str:
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
      "observed_failure_type": "none",
      "reason": "",
      "diagnostic_ir": {
        "error_type": "none",
        "error_subtype": "none",
        "stage": "none",
        "confidence": 0.95
      }
    }
  ]
}
print(json.dumps(payload))
""".strip()
    return f"python3 -c {shlex.quote(code)}"


class RunAgentModelicaL4ChallengePackV0ScriptTests(unittest.TestCase):
    def _taskset_payload(self, model_path: str) -> dict:
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

    def test_script_passes_when_baseline_range_allows_100(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_challenge_pack_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A1.mo"
            model.write_text("model A1\nend A1;\n", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps(self._taskset_payload(str(model))), encoding="utf-8")
            out_dir = root / "pack"

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_always_pass(),
                "GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND": "gemini",
                "GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL": "gemini-3.1-pro-preview",
                "GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT": "90",
                "GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT": "100",
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC": "20",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=300,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "frozen_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(float(summary.get("baseline_off_success_at_k_pct") or 0.0), 100.0)
            provenance = summary.get("baseline_provenance") if isinstance(summary.get("baseline_provenance"), dict) else {}
            self.assertEqual(str(provenance.get("planner_backend") or ""), "gemini")
            self.assertEqual(str(provenance.get("llm_model") or ""), "gemini-3.1-pro-preview")
            self.assertTrue(str(provenance.get("live_executor_cmd_sha256") or ""))
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("baseline_provenance", manifest)

    def test_script_fails_when_baseline_out_of_range(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_challenge_pack_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A1.mo"
            model.write_text("model A1\nend A1;\n", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps(self._taskset_payload(str(model))), encoding="utf-8")
            out_dir = root / "pack"

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_always_pass(),
                "GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT": "60",
                "GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT": "90",
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE": "1",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=300,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "frozen_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("baseline_off_success_out_of_target_range", set(summary.get("reasons") or []))
            self.assertEqual(int(summary.get("baseline_summary_refresh_exit_code") or 0), 1)
            self.assertIn("baseline_provenance", summary)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("baseline_provenance", manifest)

    def test_script_keeps_provenance_when_baseline_out_of_range_but_enforcement_disabled(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_challenge_pack_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A1.mo"
            model.write_text("model A1\nend A1;\n", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps(self._taskset_payload(str(model))), encoding="utf-8")
            out_dir = root / "pack"

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_always_pass(),
                "GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND": "gemini",
                "GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL": "gemini-3.1-pro-preview",
                "GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT": "60",
                "GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT": "90",
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE": "0",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=300,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "frozen_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertEqual(int(summary.get("baseline_summary_refresh_exit_code") or 0), 1)
            self.assertIn("baseline_off_success_out_of_target_range", set(summary.get("reasons") or []))
            provenance = summary.get("baseline_provenance") if isinstance(summary.get("baseline_provenance"), dict) else {}
            self.assertEqual(str(provenance.get("planner_backend") or ""), "gemini")
            self.assertEqual(str(provenance.get("llm_model") or ""), "gemini-3.1-pro-preview")
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("baseline_provenance", manifest)


if __name__ == "__main__":
    unittest.main()
