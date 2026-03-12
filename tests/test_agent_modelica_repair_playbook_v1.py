import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_repair_playbook_v1 import load_repair_playbook, recommend_repair_strategy


class AgentModelicaRepairPlaybookV1Tests(unittest.TestCase):
    def test_underconstrained_strategy_prioritizes_topology_restore(self) -> None:
        payload = load_repair_playbook(None)
        rec = recommend_repair_strategy(payload, failure_type="underconstrained_system", expected_stage="check")
        actions = rec.get("actions") if isinstance(rec.get("actions"), list) else []
        self.assertGreaterEqual(len(actions), 4)
        self.assertIn("missing connect", actions[0])
        self.assertIn("dangling conservation path", actions[1])
        self.assertIn("minimal topology", actions[2])
        self.assertIn("underconstraint probes", actions[3])
        self.assertIn("equation rewrite", actions[4])

    def test_build_playbook_from_corpus_and_recommend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            corpus = root / "corpus.json"
            out = root / "playbook.json"
            corpus.write_text(
                json.dumps(
                    {
                        "rows": [
                            {"failure_type": "model_check_error", "expected_stage": "check"},
                            {"failure_type": "simulate_error", "expected_stage": "simulate"},
                            {"failure_type": "semantic_regression", "expected_stage": "simulate"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_repair_playbook_v1",
                    "--corpus",
                    str(corpus),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = load_repair_playbook(str(out))
            rec = recommend_repair_strategy(payload, failure_type="simulate_error", expected_stage="simulate")
            self.assertEqual(rec.get("strategy_id"), "sim_init_stability")
            self.assertGreaterEqual(float(rec.get("confidence", 0.0)), 0.7)


if __name__ == "__main__":
    unittest.main()
