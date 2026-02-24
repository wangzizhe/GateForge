import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneGovernanceHistoryTests(unittest.TestCase):
    def test_history_summary_from_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            r1.write_text(
                json.dumps({"advisor_profile": "default", "effectiveness_decision": "UNCHANGED", "delta_apply_score": 0}),
                encoding="utf-8",
            )
            r2.write_text(
                json.dumps({"advisor_profile": "industrial_strict", "effectiveness_decision": "REGRESSED", "delta_apply_score": -1}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_governance_history",
                    "--record",
                    str(r1),
                    "--record",
                    str(r2),
                    "--ledger",
                    str(ledger),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("latest_effectiveness_decision"), "REGRESSED")
            self.assertIsInstance(payload.get("regression_rate"), float)


if __name__ == "__main__":
    unittest.main()
