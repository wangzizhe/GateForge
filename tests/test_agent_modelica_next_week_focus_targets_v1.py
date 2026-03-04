import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaNextWeekFocusTargetsV1Tests(unittest.TestCase):
    def test_extract_targets_from_focus_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary = root / "summary.json"
            out = root / "targets.json"
            summary.write_text(
                json.dumps(
                    {
                        "week_tag": "2026-W10",
                        "queue": [
                            {
                                "rank": 1,
                                "failure_type": "simulate_error",
                                "objective": "raise_treatment_pass_rate",
                                "action_hint": "focus_simulate_error",
                                "count": 10,
                                "delta_pass_rate_pct": -2.0,
                                "delta_avg_elapsed_sec": 1.0,
                            },
                            {
                                "rank": 2,
                                "failure_type": "semantic_regression",
                                "objective": "reduce_elapsed_time",
                                "action_hint": "focus_semantic_regression",
                                "count": 8,
                                "delta_pass_rate_pct": 0.0,
                                "delta_avg_elapsed_sec": 0.5,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_next_week_focus_targets_v1",
                    "--focus-summary",
                    str(summary),
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
            self.assertEqual(int(payload.get("target_count", 0)), 2)
            self.assertEqual((payload.get("targets") or [])[0].get("failure_type"), "simulate_error")


if __name__ == "__main__":
    unittest.main()
