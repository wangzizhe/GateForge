import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class AgentModelicaProblemPlanExecutionV1Tests(unittest.TestCase):
    def test_plan_execution_fails_when_plan_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(Path(d) / "missing_plan.json"),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(Path(d) / "out"),
                },
                timeout=60,
            )
            self.assertNotEqual(proc.returncode, 0)
            merged = (proc.stdout or "") + (proc.stderr or "")
            self.assertIn("plan_missing", merged)

    def test_plan_execution_builds_mapping_summary_before_phase_runs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "plan_rows": [
                            {"failure_type": "underconstrained_system", "target_mutant_count": 10},
                            {"failure_type": "semantic_regression", "target_mutant_count": 5},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(plan),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(root / "out"),
                    "GATEFORGE_AGENT_MUTATION_BATCH_RUNNER": str(root / "missing_runner.sh"),
                },
                timeout=60,
            )
            self.assertNotEqual(proc.returncode, 0)
            merged = (proc.stdout or "") + (proc.stderr or "")
            self.assertIn("runner_missing", merged)


if __name__ == "__main__":
    unittest.main()
