from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_runtime_context_v1 import (
    AgentModelicaRuntimeContext,
    resolve_planner_backend_from_env,
)


class AgentModelicaRuntimeContextV1Tests(unittest.TestCase):
    def test_resolve_planner_backend_from_env_prefers_gemini(self) -> None:
        with patch.dict("os.environ", {"GEMINI_API_KEY": "x"}, clear=False):
            self.assertEqual(resolve_planner_backend_from_env(), "gemini")

    def test_resolve_planner_backend_from_env_uses_openai(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "x", "GEMINI_API_KEY": ""}, clear=False):
            self.assertEqual(resolve_planner_backend_from_env(), "openai")

    def test_create_builds_protocol_and_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_runtime_ctx_") as td:
            root = Path(td)
            src = root / "source.mo"
            mutated = root / "mutated.mo"
            out = root / "result.json"
            src.write_text("model A\nend A;\n", encoding="utf-8")
            mutated.write_text("model A\nend A;\n", encoding="utf-8")
            ctx = AgentModelicaRuntimeContext.create(
                task_id="case_a",
                run_id="run_01",
                arm_kind="gateforge",
                profile_id="repair-executor",
                artifact_root=root,
                source_model_path=src,
                mutated_model_path=mutated,
                result_path=out,
                declared_failure_type="simulate_error",
                expected_stage="simulate",
                max_rounds=5,
                simulate_stop_time=10.0,
                simulate_intervals=500,
                timeout_sec=600,
                planner_backend="gemini",
                enabled_policy_flags={
                    "allow_baseline_single_sweep": True,
                    "allow_new_multistep_policy": False,
                },
            )
            self.assertEqual(ctx.planner_backend, "gemini")
            self.assertEqual(ctx.arm_kind, "gateforge")
            self.assertEqual(ctx.profile_id, "repair-executor")
            self.assertEqual(
                ctx.baseline_measurement_protocol["baseline_lever_name"],
                "simulate_error_parameter_recovery_sweep",
            )
            self.assertEqual(ctx.baseline_measurement_protocol["profile_id"], "repair-executor")
            self.assertFalse(ctx.baseline_measurement_protocol["enabled_policy_flags"]["allow_new_multistep_policy"])
            cmd = ctx.executor_command()
            self.assertIn("--planner-backend", cmd)
            self.assertIn("gemini", cmd)
            self.assertIn("--task-id", cmd)
            self.assertIn("case_a", cmd)

    def test_write_json_persists_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_runtime_ctx_write_") as td:
            root = Path(td)
            src = root / "source.mo"
            mutated = root / "mutated.mo"
            out = root / "result.json"
            target = root / "runtime_context.json"
            src.write_text("model A\nend A;\n", encoding="utf-8")
            mutated.write_text("model A\nend A;\n", encoding="utf-8")
            ctx = AgentModelicaRuntimeContext.create(
                task_id="case_b",
                run_id="run_02",
                arm_kind="gateforge",
                profile_id="repair-executor",
                artifact_root=root,
                source_model_path=src,
                mutated_model_path=mutated,
                result_path=out,
                declared_failure_type="simulate_error",
                expected_stage="simulate",
                max_rounds=5,
                simulate_stop_time=10.0,
                simulate_intervals=500,
                timeout_sec=600,
                planner_backend="gemini",
            )
            ctx.write_json(target)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["task_id"], "case_b")
            self.assertEqual(payload["run_id"], "run_02")
            self.assertEqual(payload["baseline_measurement_protocol"]["protocol_version"], "v0_3_6_single_sweep_baseline_authority_v1")
