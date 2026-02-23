import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReplayCompareTests(unittest.TestCase):
    def _write_compare_summary(self, path: Path, *, status: str = "PASS", best_decision: str = "PASS") -> None:
        path.write_text(
            json.dumps(
                {
                    "status": status,
                    "best_profile": "default",
                    "best_decision": best_decision,
                    "recommended_profile": "default",
                    "best_reason": "highest_total_score",
                    "best_total_score": 200,
                    "top_score_margin": 2,
                    "min_top_score_margin": 1,
                    "decision_explanations": {
                        "best_vs_others": [
                            {
                                "winner_profile": "default",
                                "challenger_profile": "industrial_strict",
                                "score_margin": 2,
                                "tie_on_total_score": False,
                                "winner_advantages": ["decision_component"],
                                "score_breakdown_delta": {
                                    "decision_component": 100,
                                    "exit_component": 0,
                                    "reasons_component": 0,
                                    "recommended_component": 3,
                                    "total_score": 103,
                                },
                                "ranked_advantages": [
                                    {"component": "decision_component", "delta": 100},
                                    {"component": "recommended_component", "delta": 3},
                                ],
                            }
                        ]
                    },
                    "explanation_quality": {"score": 100},
                }
            ),
            encoding="utf-8",
        )

    def test_replay_compare_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "summary.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_compare",
                    "--compare-summary",
                    str(compare),
                    "--profiles",
                    "default",
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
            self.assertEqual(payload.get("best_profile"), "default")
            self.assertEqual(len(payload.get("profile_results", [])), 1)

    def test_replay_compare_strict_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "summary.json"
            self._write_compare_summary(compare, status="FAIL", best_decision="FAIL")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_compare",
                    "--compare-summary",
                    str(compare),
                    "--profiles",
                    "default",
                    "industrial_strict",
                    "--strict",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            self.assertGreaterEqual(len(payload.get("profile_results", [])), 1)


if __name__ == "__main__":
    unittest.main()
