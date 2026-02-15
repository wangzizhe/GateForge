import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepairOrchestrateTests(unittest.TestCase):
    def test_repair_orchestrate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            out_dir = root / "out"
            out = root / "summary.json"
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "orchestrate-001",
                        "status": "FAIL",
                        "policy_decision": "FAIL",
                        "risk_level": "low",
                        "policy_reasons": ["runtime_regression:1.2s>1.0s"],
                        "fail_reasons": ["regression_fail"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_orchestrate",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--strategy-profile",
                    "default",
                    "--baseline",
                    "baselines/mock_minimal_probe_baseline.json",
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
            self.assertTrue((out_dir / "tasks.json").exists())
            self.assertTrue((out_dir / "pack.json").exists())
            self.assertTrue((out_dir / "batch_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
