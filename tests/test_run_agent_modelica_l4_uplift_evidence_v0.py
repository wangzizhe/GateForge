import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _cmd_pass() -> str:
    return "python3 -m gateforge.agent_modelica_live_executor_mock_v0"


def _cmd_l4_switch() -> str:
    return 'python3 -m gateforge.agent_modelica_live_executor_mock_l4_switch_v0 --l4-enabled "__L4_ENABLED__"'


def _build_taskset(path: Path) -> None:
    payload = {
        "schema_version": "agent_modelica_taskset_v0",
        "tasks": [
            {
                "task_id": "t_model_check_small",
                "scale": "small",
                "failure_type": "model_check_error",
                "expected_stage": "check",
            },
            {
                "task_id": "t_simulate_medium",
                "scale": "medium",
                "failure_type": "simulate_error",
                "expected_stage": "simulate",
            },
            {
                "task_id": "t_semantic_small",
                "scale": "small",
                "failure_type": "semantic_regression",
                "expected_stage": "simulate",
            },
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class RunAgentModelicaL4UpliftEvidenceV0ScriptTests(unittest.TestCase):
    def test_full_chain_outputs_promote_with_mock(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_uplift_evidence_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            _build_taskset(taskset)

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_UPLIFT_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_UPLIFT_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MIN_OFF_SUCCESS_PCT": "0",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MAX_OFF_SUCCESS_PCT": "100",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
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
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "PASS")
            self.assertEqual(str(decision.get("decision") or ""), "promote")
            self.assertEqual(str(decision.get("primary_reason") or ""), "none")
            self.assertGreaterEqual(float(decision.get("main_delta_success_at_k_pp") or 0.0), 5.0)

    def test_weak_baseline_short_circuits_to_hold(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_uplift_evidence_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out_hold"
            _build_taskset(taskset)

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_UPLIFT_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_UPLIFT_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=600,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "PASS")
            self.assertEqual(str(decision.get("decision") or ""), "hold")
            self.assertEqual(str(decision.get("primary_reason") or ""), "baseline_too_weak")


if __name__ == "__main__":
    unittest.main()
