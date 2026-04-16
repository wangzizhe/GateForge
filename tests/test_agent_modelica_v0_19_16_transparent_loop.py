from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gateforge.agent_modelica_live_executor_v1 as _executor_module
from gateforge.agent_modelica_live_executor_v1 import _parse_main_args


class V01916TransparentLoopTests(unittest.TestCase):
    def test_parse_main_args_defaults_transparent_loop_on(self) -> None:
        with patch.object(sys, "argv", ["agent_modelica_live_executor_v1"]):
            args = _parse_main_args()

        self.assertEqual(args.transparent_repair_loop, "on")

    def test_main_rejects_transparent_loop_off(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v01916_transparent_off_") as td:
            root = Path(td)
            model_path = root / "Demo.mo"
            model_path.write_text("model Demo\nend Demo;\n", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "agent_modelica_live_executor_v1",
                    "--task-id",
                    "transparent-off-demo",
                    "--mutated-model-path",
                    str(model_path),
                    "--transparent-repair-loop",
                    "off",
                    "--planner-backend",
                    "rule",
                ],
            ):
                with self.assertRaisesRegex(ValueError, "transparent_repair_loop_off_is_not_supported_in_v0_19_16"):
                    _executor_module.main()

    def test_main_marks_attempts_as_transparent_loop(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v01916_transparent_pass_") as td:
            root = Path(td)
            model_path = root / "Demo.mo"
            out_path = root / "out.json"
            model_path.write_text(
                "model Demo\n"
                "  Real x;\n"
                "equation\n"
                "  der(x) = -x;\n"
                "end Demo;\n",
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "agent_modelica_live_executor_v1",
                    "--task-id",
                    "transparent-pass-demo",
                    "--mutated-model-path",
                    str(model_path),
                    "--planner-backend",
                    "rule",
                    "--backend",
                    "omc",
                    "--max-rounds",
                    "1",
                    "--out",
                    str(out_path),
                ],
            ), patch(
                "gateforge.agent_modelica_live_executor_v1._run_check_and_simulate",
                return_value=(0, "Check of Demo completed successfully.", True, True),
            ), patch(
                "gateforge.agent_modelica_live_executor_v1.build_diagnostic_ir_v0",
                return_value={"error_type": "none", "reason": ""},
            ), patch("builtins.print"):
                _executor_module.main()

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("executor_status"), "PASS")
            attempts = payload.get("attempts")
            self.assertIsInstance(attempts, list)
            self.assertEqual(len(attempts), 1)
            self.assertTrue(bool(attempts[0].get("transparent_repair_loop")))
            self.assertTrue(bool(attempts[0].get("check_model_pass")))
            self.assertTrue(bool(attempts[0].get("simulate_pass")))


if __name__ == "__main__":
    unittest.main()
