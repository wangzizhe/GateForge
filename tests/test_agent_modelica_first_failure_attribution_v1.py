import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaFirstFailureAttributionV1Tests(unittest.TestCase):
    def test_extracts_first_attempt_observed_type_and_pre_repair(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_results = root / "run_results.json"
            out = root / "first_attr.json"
            run_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "repair_audit": {"strategy_id": "mc_a", "actions_planned": ["a1"]},
                                "attempts": [
                                    {
                                        "check_model_pass": False,
                                        "simulate_pass": False,
                                        "physics_contract_pass": False,
                                        "regression_pass": False,
                                        "observed_failure_type": "script_parse_error",
                                        "reason": "compile/syntax error",
                                        "pre_repair": {"applied": True, "reason": "removed_lines_with_injected_state_tokens"},
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_first_failure_attribution_v1",
                    "--run-results",
                    str(run_results),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.get("first_observed_failure_type"), "script_parse_error")
            self.assertEqual(row.get("first_gate_break_reason"), "check_model_fail")
            self.assertTrue(bool(row.get("first_pre_repair_applied")))


if __name__ == "__main__":
    unittest.main()
