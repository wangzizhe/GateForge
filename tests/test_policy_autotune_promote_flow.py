import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotunePromoteFlowTests(unittest.TestCase):
    def test_flow_runs_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            advisor = root / "advisor.json"
            out = root / "flow.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "kpis": {
                            "strict_downgrade_rate": 0.0,
                            "downgrade_count": 0,
                            "strategy_compare_relation": "unchanged",
                            "recommended_profile": "default",
                            "review_recovery_rate": 0.8,
                            "strict_non_pass_rate": 0.1,
                            "approval_rate": 0.8,
                            "fail_rate": 0.1,
                        },
                        "risks": [],
                    }
                ),
                encoding="utf-8",
            )
            advisor.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "default",
                            "threshold_patch": {"require_min_top_score_margin": 1},
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_promote_flow",
                    "--snapshot",
                    str(snapshot),
                    "--advisor",
                    str(advisor),
                    "--out-dir",
                    str(root / "out"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("baseline", {}).get("compare_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(payload.get("tuned", {}).get("compare_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})


if __name__ == "__main__":
    unittest.main()
