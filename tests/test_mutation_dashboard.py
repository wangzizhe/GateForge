import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutationDashboardTests(unittest.TestCase):
    def test_dashboard_bundle_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            metrics = root / "metrics.json"
            history = root / "history.json"
            trend = root / "trend.json"
            compare = root / "compare.json"
            out = root / "summary.json"
            metrics.write_text(
                json.dumps(
                    {
                        "pack_id": "mutation_pack_v1",
                        "pack_version": "v1",
                        "expected_vs_actual_match_rate": 1.0,
                        "gate_pass_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            history.write_text(json.dumps({"total_records": 2}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "PASS", "trend": {"delta_match_rate": 0.1, "delta_gate_pass_rate": 0.1}}), encoding="utf-8")
            compare.write_text(json.dumps({"decision": "PASS", "delta_match_rate": 0.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutation_dashboard",
                    "--metrics",
                    str(metrics),
                    "--history",
                    str(history),
                    "--trend",
                    str(trend),
                    "--compare",
                    str(compare),
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
            self.assertEqual(payload.get("latest_pack_id"), "mutation_pack_v1")


if __name__ == "__main__":
    unittest.main()
