import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneEffectivenessTests(unittest.TestCase):
    def test_effectiveness_detects_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            flow = root / "flow.json"
            out = root / "effectiveness.json"
            flow.write_text(
                json.dumps(
                    {
                        "baseline": {"compare_status": "NEEDS_REVIEW", "apply_status": "NEEDS_REVIEW"},
                        "tuned": {"compare_status": "PASS", "apply_status": "PASS"},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_effectiveness",
                    "--flow-summary",
                    str(flow),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "IMPROVED")
            self.assertGreater(payload.get("delta_apply_score", 0), 0)


if __name__ == "__main__":
    unittest.main()
