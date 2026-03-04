import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaPlaybookFocusUpdateV1Tests(unittest.TestCase):
    def test_focus_update_boosts_top_failure_entries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            playbook = root / "playbook.json"
            queue = root / "queue.json"
            out = root / "focused.json"
            playbook.write_text(
                json.dumps(
                    {
                        "playbook": [
                            {
                                "failure_type": "simulate_error",
                                "strategy_id": "sim_a",
                                "priority": 80,
                                "actions": ["baseline action"],
                            },
                            {
                                "failure_type": "model_check_error",
                                "strategy_id": "mc_a",
                                "priority": 70,
                                "actions": ["baseline action"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            queue.write_text(
                json.dumps({"queue": [{"failure_type": "simulate_error", "rank": 1}]}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_playbook_focus_update_v1",
                    "--playbook",
                    str(playbook),
                    "--queue",
                    str(queue),
                    "--priority-boost",
                    "10",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            entries = payload.get("playbook", [])
            sim = [x for x in entries if x.get("failure_type") == "simulate_error"][0]
            self.assertEqual(int(sim.get("priority", 0)), 90)
            self.assertEqual(sim.get("focus_tag"), "top_failure_focus")


if __name__ == "__main__":
    unittest.main()
