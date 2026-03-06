import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaMutationPlanBuilderV1Tests(unittest.TestCase):
    def test_build_plan_from_taxonomy_and_quota(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taxonomy = root / "taxonomy.json"
            quota = root / "quota.json"
            plan = root / "plan.json"
            summary = root / "summary.json"
            taxonomy.write_text(
                json.dumps(
                    {
                        "problem_types": [
                            {
                                "failure_type": "underconstrained_system",
                                "expected_stage": "check",
                                "category": "equation_balance",
                                "severity": "high",
                                "mutation_operators": ["drop_state_equation", "remove_conservation_constraint"],
                            },
                            {
                                "failure_type": "numerical_instability",
                                "expected_stage": "simulate",
                                "category": "numerics",
                                "severity": "high",
                                "mutation_operators": ["inject_stiff_gain_blowup", "remove_damping_term"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            quota.write_text(
                json.dumps(
                    {
                        "default_target_per_scale_failure_type": {"small": 3, "medium": 4, "large": 5},
                        "failure_type_overrides": {"underconstrained_system": {"small": 7}},
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_mutation_plan_builder_v1",
                    "--taxonomy",
                    str(taxonomy),
                    "--quota-profile",
                    str(quota),
                    "--plan-out",
                    str(plan),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            rows = json.loads(plan.read_text(encoding="utf-8")).get("plan_rows") or []
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("total_plan_rows", 0)), 6)
            self.assertGreater(int(payload.get("total_target_mutants", 0)), 0)
            match = [x for x in rows if str(x.get("failure_type")) == "underconstrained_system" and str(x.get("scale")) == "small"]
            self.assertEqual(len(match), 1)
            self.assertEqual(int(match[0].get("target_mutant_count", 0)), 7)

    def test_fail_when_taxonomy_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_mutation_plan_builder_v1",
                    "--taxonomy",
                    str(root / "missing_taxonomy.json"),
                    "--quota-profile",
                    "benchmarks/agent_modelica_problem_quota_v1.json",
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
            self.assertIn("problem_taxonomy_missing_or_empty", reasons)


if __name__ == "__main__":
    unittest.main()
