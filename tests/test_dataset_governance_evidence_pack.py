import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceEvidencePackTests(unittest.TestCase):
    def test_pack_pass_with_complete_sources(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            taxonomy = root / "taxonomy.json"
            distribution = root / "distribution.json"
            ladder = root / "ladder.json"
            advisor = root / "advisor.json"
            backlog = root / "backlog.json"
            replay_eval = root / "replay_eval.json"
            out = root / "summary.json"

            snapshot.write_text(json.dumps({"status": "PASS", "risks": [], "kpis": {}}), encoding="utf-8")
            trend.write_text(
                json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS", "severity_score": 0, "severity_level": "low"}}),
                encoding="utf-8",
            )
            taxonomy.write_text(json.dumps({"status": "PASS", "alerts": []}), encoding="utf-8")
            distribution.write_text(json.dumps({"status": "PASS", "alerts": []}), encoding="utf-8")
            ladder.write_text(json.dumps({"status": "PASS", "alerts": []}), encoding="utf-8")
            advisor.write_text(json.dumps({"status": "PASS", "advice": {"suggested_action": "keep"}}), encoding="utf-8")
            backlog.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "total_open_tasks": 2, "priority_counts": {"P0": 1}}),
                encoding="utf-8",
            )
            replay_eval.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "recommendation": "ADOPT_PATCH",
                        "evaluation_score": 4,
                        "delta": {"detection_rate": 0.05, "false_positive_rate": -0.02, "regression_rate": -0.03},
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_evidence_pack",
                    "--snapshot-summary",
                    str(snapshot),
                    "--snapshot-trend",
                    str(trend),
                    "--failure-taxonomy-coverage",
                    str(taxonomy),
                    "--failure-distribution-benchmark",
                    str(distribution),
                    "--model-scale-ladder",
                    str(ladder),
                    "--failure-policy-patch-advisor",
                    str(advisor),
                    "--blind-spot-backlog",
                    str(backlog),
                    "--policy-patch-replay-evaluator",
                    str(replay_eval),
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
            self.assertEqual((payload.get("integrity") or {}).get("status"), "PASS")
            self.assertEqual((payload.get("action_outcome") or {}).get("replay_recommendation"), "ADOPT_PATCH")

    def test_pack_fail_on_integrity_break(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            out = root / "summary.json"

            snapshot.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "PASS", "trend": {}}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_evidence_pack",
                    "--snapshot-summary",
                    str(snapshot),
                    "--snapshot-trend",
                    str(trend),
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
            self.assertEqual((payload.get("integrity") or {}).get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
