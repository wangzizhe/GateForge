import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaTop2WeightSweepV1Tests(unittest.TestCase):
    def test_weight_sweep_outputs_best_config(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            playbook = root / "playbook.json"
            out_dir = root / "out"
            out = root / "summary.json"

            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "e1",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "observed_elapsed_sec": 40,
                                "observed_repair_rounds": 2,
                                "baseline_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                                "candidate_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                            },
                            {
                                "task_id": "e2",
                                "scale": "medium",
                                "failure_type": "model_check_error",
                                "expected_stage": "check_model",
                                "observed_elapsed_sec": 40,
                                "observed_repair_rounds": 2,
                                "baseline_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                                "candidate_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {"runtime_seconds": 40.0},
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            playbook.write_text(
                json.dumps(
                    {
                        "playbook": [
                            {
                                "failure_type": "simulate_error",
                                "strategy_id": "sim_stage",
                                "name": "sim",
                                "priority": 100,
                                "actions": ["a"],
                                "preferred_stage": "simulate",
                            },
                            {
                                "failure_type": "model_check_error",
                                "strategy_id": "mc_stage",
                                "name": "mc",
                                "priority": 100,
                                "actions": ["a"],
                                "preferred_stage": "check_model",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_top2_weight_sweep_v1",
                    "--taskset",
                    str(taskset),
                    "--base-playbook",
                    str(playbook),
                    "--weight-triples",
                    "0.8,0.2,0.8;0.7,0.3,0.8",
                    "--out-dir",
                    str(out_dir),
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
            self.assertEqual(int(payload.get("run_count", 0)), 2)
            self.assertIsInstance(payload.get("best_config"), dict)


if __name__ == "__main__":
    unittest.main()
