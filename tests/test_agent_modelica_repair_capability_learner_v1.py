import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_repair_capability_learner_v1 import learn_capability_assets


class AgentModelicaRepairCapabilityLearnerV1Tests(unittest.TestCase):
    def test_learn_capability_assets_extracts_actions_and_policy(self) -> None:
        memory = {
            "rows": [
                {
                    "failure_type": "simulate_error",
                    "status": "PASS",
                    "used_strategy": "sim_init_stability",
                    "action_trace": ["stabilize start values", "bound parameters"],
                },
                {
                    "failure_type": "simulate_error",
                    "status": "PASS",
                    "used_strategy": "sim_init_stability",
                    "action_trace": ["stabilize start values"],
                },
                {
                    "failure_type": "simulate_error",
                    "status": "PASS",
                    "used_strategy": "sim_solver_guard",
                    "action_trace": ["reduce chattering"],
                },
            ]
        }
        payload = learn_capability_assets(memory_payload=memory, min_success_count_per_failure_type=2)
        self.assertEqual(int(payload.get("learned_failure_type_count", 0)), 1)
        adaptations = payload.get("patch_template_adaptations", {}).get("simulate_error", {})
        self.assertIn("stabilize start values", adaptations.get("actions", []))
        self.assertEqual(int((adaptations.get("action_frequency") or {}).get("stabilize start values", 0)), 2)
        retrieval_policy = payload.get("retrieval_policy", {})
        self.assertTrue(int(retrieval_policy.get("top_k_by_failure_type", {}).get("simulate_error", 0)) >= 2)

    def test_cli_writes_private_assets(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            memory = root / "memory.json"
            out_patch = root / "patch.json"
            out_policy = root / "policy.json"
            out_summary = root / "summary.json"
            memory.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "failure_type": "model_check_error",
                                "status": "PASS",
                                "used_strategy": "mc_symbol_guard",
                                "action_trace": ["declare missing symbols"],
                            },
                            {
                                "failure_type": "model_check_error",
                                "status": "PASS",
                                "used_strategy": "mc_symbol_guard",
                                "action_trace": ["align connectors"],
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
                    "gateforge.agent_modelica_repair_capability_learner_v1",
                    "--repair-memory",
                    str(memory),
                    "--min-success-count-per-failure-type",
                    "2",
                    "--out-patch-template-adaptations",
                    str(out_patch),
                    "--out-retrieval-policy",
                    str(out_policy),
                    "--out",
                    str(out_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertTrue(out_patch.exists())
            self.assertTrue(out_policy.exists())
            self.assertTrue(out_summary.exists())
            summary = json.loads(out_summary.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")


if __name__ == "__main__":
    unittest.main()
