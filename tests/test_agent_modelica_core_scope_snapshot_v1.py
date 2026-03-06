import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaCoreScopeSnapshotV1Tests(unittest.TestCase):
    def test_snapshot_passes_when_all_core_paths_exist(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "gateforge").mkdir(parents=True, exist_ok=True)
            (root / "scripts" / "run_agent_modelica_weekly_chain_v1.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / "gateforge" / "agent_modelica_run_contract_v1.py").write_text("pass\n", encoding="utf-8")

            scope = root / "scope.json"
            scope.write_text(
                json.dumps(
                    {
                        "scope_version": "v1",
                        "scope_name": "core",
                        "core_paths": [
                            "scripts/run_agent_modelica_weekly_chain_v1.sh",
                            "gateforge/agent_modelica_run_contract_v1.py",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = root / "snapshot.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_core_scope_snapshot_v1",
                    "--repo-root",
                    str(root),
                    "--scope",
                    str(scope),
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
            self.assertEqual(int(payload.get("core_path_count", 0)), 2)
            self.assertEqual(int(payload.get("core_existing_count", 0)), 2)


if __name__ == "__main__":
    unittest.main()
