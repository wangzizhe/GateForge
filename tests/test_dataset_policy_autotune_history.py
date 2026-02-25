import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyAutotuneHistoryTests(unittest.TestCase):
    def test_history_summary_builds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            advisor.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "dataset_strict",
                            "suggested_action": "tighten_generation_controls",
                            "confidence": 0.86,
                            "reasons": ["x", "y"],
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_autotune_history",
                    "--record",
                    str(advisor),
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
            self.assertEqual(payload.get("total_records"), 1)
            self.assertEqual(payload.get("latest_suggested_profile"), "dataset_strict")
            self.assertIn("latest_suggests_tighten", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()

