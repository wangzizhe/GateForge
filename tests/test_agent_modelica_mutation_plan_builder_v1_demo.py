import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class AgentModelicaMutationPlanBuilderV1DemoTests(unittest.TestCase):
    def test_demo_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_agent_modelica_mutation_plan_builder_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"},
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            out = repo_root / "artifacts" / "agent_modelica_mutation_plan_builder_v1_demo"
            summary = json.loads((out / "demo_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("bundle_status"), "PASS")
            self.assertGreaterEqual(int(summary.get("failure_type_count", 0) or 0), 10)


if __name__ == "__main__":
    unittest.main()
