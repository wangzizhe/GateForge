import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneHistoryTests(unittest.TestCase):
    def test_history_summary_from_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a1 = root / "a1.json"
            a2 = root / "a2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            a1.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "default",
                            "confidence": 0.6,
                            "reasons": ["stable"],
                            "threshold_patch": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
            a2.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "industrial_strict",
                            "confidence": 0.9,
                            "reasons": ["regressed"],
                            "threshold_patch": {
                                "require_min_top_score_margin": 2,
                                "require_min_explanation_quality": 85,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_history",
                    "--record",
                    str(a1),
                    "--record",
                    str(a2),
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
            self.assertEqual(payload.get("latest_suggested_profile"), "industrial_strict")
            self.assertIsInstance(payload.get("strict_suggestion_rate"), float)


if __name__ == "__main__":
    unittest.main()
