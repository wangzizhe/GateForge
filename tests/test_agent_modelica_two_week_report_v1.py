import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaTwoWeekReportV1Tests(unittest.TestCase):
    def test_builds_fixed_two_week_report(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w1 = root / "w1.json"
            w2 = root / "w2.json"
            decision = root / "decision.json"
            out = root / "report.json"
            w1.write_text(
                json.dumps(
                    {
                        "week_tag": "w1",
                        "success_at_k_pct": 90.0,
                        "median_time_to_pass_sec": 80.0,
                        "median_repair_rounds": 3.0,
                        "regression_count": 1,
                        "physics_fail_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            w2.write_text(
                json.dumps(
                    {
                        "week_tag": "w2",
                        "success_at_k_pct": 95.0,
                        "median_time_to_pass_sec": 70.0,
                        "median_repair_rounds": 2.0,
                        "regression_count": 0,
                        "physics_fail_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            decision.write_text(json.dumps({"decision": "PROMOTE"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_two_week_report_v1",
                    "--week1-summary",
                    str(w1),
                    "--week2-summary",
                    str(w2),
                    "--decision",
                    str(decision),
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
            self.assertEqual(payload.get("decision"), "PROMOTE")
            self.assertEqual((payload.get("delta") or {}).get("success_at_k_pct"), 5.0)
            self.assertEqual((payload.get("delta") or {}).get("median_time_to_pass_sec"), -10.0)


if __name__ == "__main__":
    unittest.main()
