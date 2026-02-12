import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PlannerTests(unittest.TestCase):
    def test_planner_runtime_high_risk_intent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "intent.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal",
                    "Please evaluate a high risk runtime regression",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["intent"], "runtime_regress_high_risk")
            self.assertEqual(payload["overrides"]["risk_level"], "high")

    def test_planner_prefer_openmodelica(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "intent.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal",
                    "run a simple pass flow",
                    "--prefer-backend",
                    "openmodelica_docker",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["intent"], "demo_openmodelica_pass")

    def test_planner_with_agent_run_integration(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intent_out = root / "intent.json"
            agent_out = root / "agent_run.json"
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "run_id": "base-planner-1",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "status": "success",
                        "gate": "PASS",
                        "check_ok": True,
                        "simulate_ok": True,
                        "metrics": {"runtime_seconds": 0.1},
                    }
                ),
                encoding="utf-8",
            )

            proc_plan = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "planner-integration-1",
                    "--out",
                    str(intent_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_plan.returncode, 0, msg=proc_plan.stderr or proc_plan.stdout)

            proc_run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_run",
                    "--intent-file",
                    str(intent_out),
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(agent_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_run.returncode, 0, msg=proc_run.stderr or proc_run.stdout)
            payload = json.loads(agent_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["proposal_id"], "planner-integration-1")
            self.assertEqual(payload["status"], "PASS")

    def test_planner_goal_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "intent.json"
            goal_file = root / "goal.txt"
            goal_file.write_text("Please run medium oscillator flow", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal-file",
                    str(goal_file),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["intent"], "medium_openmodelica_pass")
            self.assertEqual(payload["planner_inputs"]["goal"], "Please run medium oscillator flow")

    def test_planner_context_json_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "intent.json"
            context = root / "context.json"
            context.write_text(
                json.dumps(
                    {
                        "prefer_backend": "openmodelica_docker",
                        "risk_level": "medium",
                        "change_summary": "Context-specified summary",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal",
                    "run a simple pass flow",
                    "--context-json",
                    str(context),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["intent"], "demo_openmodelica_pass")
            self.assertEqual(payload["overrides"]["risk_level"], "medium")
            self.assertEqual(payload["overrides"]["change_summary"], "Context-specified summary")
            self.assertEqual(payload["planner_inputs"]["prefer_backend"], "openmodelica_docker")

    def test_planner_openai_backend_requires_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "intent.json"
            env = os.environ.copy()
            env.pop("OPENAI_API_KEY", None)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal",
                    "run demo mock pass",
                    "--planner-backend",
                    "openai",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("requires OPENAI_API_KEY", proc.stderr + proc.stdout)
            self.assertFalse(out.exists())

    def test_planner_gemini_backend_requires_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "intent.json"
            env = os.environ.copy()
            env.pop("GOOGLE_API_KEY", None)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal",
                    "run demo mock pass",
                    "--planner-backend",
                    "gemini",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("requires GOOGLE_API_KEY", proc.stderr + proc.stdout)
            self.assertFalse(out.exists())

    def test_planner_rule_emits_change_set_draft(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "intent.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.llm_planner",
                    "--goal",
                    "apply a deterministic patch",
                    "--planner-backend",
                    "rule",
                    "--emit-change-set-draft",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("change_set_draft", payload)
            self.assertEqual(payload["change_set_draft"]["schema_version"], "0.1.0")


if __name__ == "__main__":
    unittest.main()
