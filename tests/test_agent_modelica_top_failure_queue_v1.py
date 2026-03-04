import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaTopFailureQueueV1Tests(unittest.TestCase):
    def test_build_top2_queue(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ab = root / "ab.json"
            out = root / "queue.json"
            ab.write_text(
                json.dumps(
                    {
                        "per_failure_type": {
                            "simulate_error": {"count": 20, "delta_pass_rate_pct": -5.0, "delta_avg_elapsed_sec": 0.5},
                            "semantic_regression": {"count": 15, "delta_pass_rate_pct": 0.0, "delta_avg_elapsed_sec": 1.0},
                            "model_check_error": {"count": 8, "delta_pass_rate_pct": 2.0, "delta_avg_elapsed_sec": 0.0},
                        },
                        "strategy_signal_by_failure_type": {
                            "treatment": {
                                "simulate_error": {"score": 0.4},
                                "semantic_regression": {"score": 0.7},
                                "model_check_error": {"score": 0.9},
                            },
                            "delta_score": {
                                "simulate_error": -0.1,
                                "semantic_regression": 0.0,
                                "model_check_error": 0.1,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_top_failure_queue_v1",
                    "--ab-summary",
                    str(ab),
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
            queue = payload.get("queue", [])
            self.assertEqual(len(queue), 2)
            self.assertEqual(queue[0].get("failure_type"), "simulate_error")
            self.assertIsInstance(queue[0].get("priority_score"), (int, float))

    def test_strategy_signal_weight_can_change_top_priority(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ab = root / "ab.json"
            out = root / "queue.json"
            ab.write_text(
                json.dumps(
                    {
                        "per_failure_type": {
                            "simulate_error": {"count": 10, "delta_pass_rate_pct": 0.0, "delta_avg_elapsed_sec": 0.0},
                            "semantic_regression": {"count": 10, "delta_pass_rate_pct": 0.0, "delta_avg_elapsed_sec": 0.0},
                        },
                        "strategy_signal_by_failure_type": {
                            "treatment": {
                                "simulate_error": {"score": 0.95},
                                "semantic_regression": {"score": 0.2},
                            },
                            "delta_score": {
                                "simulate_error": 0.2,
                                "semantic_regression": -0.3,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_top_failure_queue_v1",
                    "--ab-summary",
                    str(ab),
                    "--top-k",
                    "1",
                    "--outcome-weight",
                    "0.1",
                    "--strategy-weight",
                    "0.9",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            queue = payload.get("queue", [])
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0].get("failure_type"), "semantic_regression")


if __name__ == "__main__":
    unittest.main()
