import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneGovernanceDashboardTests(unittest.TestCase):
    def test_dashboard_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            flow = root / "flow.json"
            eff = root / "eff.json"
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "dashboard.json"
            flow.write_text(json.dumps({"advisor_profile": "default"}), encoding="utf-8")
            eff.write_text(json.dumps({"decision": "UNCHANGED", "delta_apply_score": 0, "delta_compare_score": 0}), encoding="utf-8")
            history.write_text(
                json.dumps({"total_records": 2, "improvement_rate": 0.4, "regression_rate": 0.1}),
                encoding="utf-8",
            )
            trend.write_text(json.dumps({"status": "PASS", "trend": {"alerts": []}}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_governance_dashboard",
                    "--flow-summary",
                    str(flow),
                    "--effectiveness",
                    str(eff),
                    "--history",
                    str(history),
                    "--trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertEqual(payload.get("latest_effectiveness_decision"), "UNCHANGED")


if __name__ == "__main__":
    unittest.main()
