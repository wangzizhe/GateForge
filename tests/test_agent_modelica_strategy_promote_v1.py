import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaStrategyPromoteV1Tests(unittest.TestCase):
    def test_promote_top_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ab = root / "ab.json"
            treatment = root / "playbook.json"
            out = root / "promoted.json"

            ab.write_text(
                json.dumps(
                    {
                        "decision": "PROMOTE_TREATMENT",
                        "per_failure_type": {
                            "simulate_error": {"delta_pass_rate_pct": 10.0, "delta_avg_elapsed_sec": -5.0, "count": 10},
                            "semantic_regression": {"delta_pass_rate_pct": 5.0, "delta_avg_elapsed_sec": -2.0, "count": 8},
                        },
                    }
                ),
                encoding="utf-8",
            )
            treatment.write_text(
                json.dumps(
                    {
                        "playbook": [
                            {"failure_type": "simulate_error", "strategy_id": "sim_a", "priority": 100},
                            {"failure_type": "semantic_regression", "strategy_id": "sem_a", "priority": 90},
                            {"failure_type": "model_check_error", "strategy_id": "mc_a", "priority": 80},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_strategy_promote_v1",
                    "--ab-summary",
                    str(ab),
                    "--treatment-playbook",
                    str(treatment),
                    "--top-k",
                    "2",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("promoted_count", 0)), 2)

    def test_safety_gate_blocks_promotion_when_regression_increases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ab = root / "ab.json"
            treatment = root / "playbook.json"
            out = root / "promoted.json"

            ab.write_text(
                json.dumps(
                    {
                        "decision": "PROMOTE_TREATMENT",
                        "delta": {"regression_count": 1, "physics_fail_count": 0},
                        "per_failure_type": {
                            "simulate_error": {"delta_pass_rate_pct": 10.0, "delta_avg_elapsed_sec": -5.0, "count": 10},
                        },
                    }
                ),
                encoding="utf-8",
            )
            treatment.write_text(
                json.dumps(
                    {
                        "playbook": [
                            {"failure_type": "simulate_error", "strategy_id": "sim_a", "priority": 100},
                            {"failure_type": "semantic_regression", "strategy_id": "sem_a", "priority": 90},
                            {"failure_type": "model_check_error", "strategy_id": "mc_a", "priority": 80},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_strategy_promote_v1",
                    "--ab-summary",
                    str(ab),
                    "--treatment-playbook",
                    str(treatment),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertFalse(bool(payload.get("promotion_allowed")))
            self.assertIn("regression_count_increased", payload.get("gate_reasons", []))
            # Gate closed: keep full playbook.
            self.assertEqual(int(payload.get("promoted_count", 0)), 3)


if __name__ == "__main__":
    unittest.main()
