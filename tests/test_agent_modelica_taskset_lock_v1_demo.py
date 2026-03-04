import json
import subprocess
import unittest
from pathlib import Path


class AgentModelicaTasksetLockV1DemoTests(unittest.TestCase):
    def test_demo_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_agent_modelica_taskset_lock_v1.sh"],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertTrue(Path("artifacts/agent_modelica_taskset_lock_v1_demo/taskset.json").exists())


if __name__ == "__main__":
    unittest.main()
