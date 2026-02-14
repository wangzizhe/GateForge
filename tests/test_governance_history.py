import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceHistoryTests(unittest.TestCase):
    def test_record_and_summarize_last_n(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history = root / "history"
            out = root / "summary.json"

            snapshots = [
                {"status": "PASS", "risks": []},
                {"status": "NEEDS_REVIEW", "risks": ["strict_profile_downgrade_detected"]},
                {"status": "FAIL", "risks": ["ci_matrix_failed"]},
            ]

            for i, payload in enumerate(snapshots, start=1):
                sp = root / f"s{i}.json"
                sp.write_text(json.dumps(payload), encoding="utf-8")
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "gateforge.governance_history",
                        "--history-dir",
                        str(history),
                        "--snapshot",
                        str(sp),
                        "--label",
                        f"s{i}",
                        "--last-n",
                        "3",
                        "--out",
                        str(out),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("total_records"), 3)
            self.assertEqual(summary.get("window_size"), 3)
            self.assertEqual(summary.get("latest_status"), "FAIL")
            self.assertEqual(summary.get("status_counts", {}).get("PASS"), 1)
            self.assertEqual(summary.get("status_counts", {}).get("FAIL"), 1)
            self.assertEqual(len(summary.get("transitions", [])), 2)
            self.assertGreaterEqual(summary.get("transition_kpis", {}).get("worse_count", 0), 1)
            self.assertEqual(summary.get("transition_kpis", {}).get("max_worse_streak"), 2)
            self.assertIn("consecutive_worsening_detected", summary.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
