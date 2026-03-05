import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaMvpExecSummaryV1Tests(unittest.TestCase):
    def test_builds_summary_from_artifact_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            three = root / "three.json"
            top2 = root / "top2.json"
            ab = root / "ab.json"
            challenge = root / "challenge.json"
            out = root / "summary.json"

            three.write_text(json.dumps({"rows": [{"round": 1}, {"round": 2}]}), encoding="utf-8")
            top2.write_text(json.dumps({"before_top2": [{"a": 1}], "after_top2": []}), encoding="utf-8")
            ab.write_text(json.dumps({"delta_on_minus_off": {"success_at_k_pct": 10.0, "regression_count": -2.0}}), encoding="utf-8")
            challenge.write_text(
                json.dumps({"delta": {"success_at_k_pct": 5.0, "regression_count": -1.0, "physics_fail_count": 0.0}}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_mvp_exec_summary_v1",
                    "--three-round-summary",
                    str(three),
                    "--top2-summary",
                    str(top2),
                    "--retrieval-ab-summary",
                    str(ab),
                    "--challenge-compare",
                    str(challenge),
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
            self.assertEqual(int(payload.get("three_round_records", 0)), 2)
            self.assertEqual((payload.get("retrieval_ab") or {}).get("delta_success_at_k_pct"), 10.0)


if __name__ == "__main__":
    unittest.main()
