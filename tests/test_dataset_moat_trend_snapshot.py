import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatTrendSnapshotTests(unittest.TestCase):
    def test_snapshot_pass_when_moat_score_high(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            evidence = root / "evidence.json"
            registry = root / "registry.json"
            backlog = root / "backlog.json"
            replay = root / "replay.json"
            previous = root / "previous.json"
            out = root / "summary.json"

            evidence.write_text(json.dumps({"status": "PASS", "evidence_strength_score": 80, "evidence_sections_present": 8}), encoding="utf-8")
            registry.write_text(json.dumps({"total_records": 30, "missing_model_scales": []}), encoding="utf-8")
            backlog.write_text(json.dumps({"total_open_tasks": 3, "priority_counts": {"P0": 0}}), encoding="utf-8")
            replay.write_text(json.dumps({"status": "PASS", "recommendation": "ADOPT_PATCH", "evaluation_score": 5}), encoding="utf-8")
            previous.write_text(json.dumps({"status": "NEEDS_REVIEW", "metrics": {"moat_score": 60}}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_trend_snapshot",
                    "--evidence-pack",
                    str(evidence),
                    "--failure-corpus-registry-summary",
                    str(registry),
                    "--blind-spot-backlog",
                    str(backlog),
                    "--policy-patch-replay-evaluator",
                    str(replay),
                    "--previous-snapshot",
                    str(previous),
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
            self.assertGreaterEqual(float((payload.get("metrics") or {}).get("moat_score", 0.0)), 70.0)

    def test_snapshot_fail_when_evidence_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            evidence = root / "evidence.json"
            out = root / "summary.json"
            evidence.write_text(json.dumps({"status": "FAIL", "evidence_strength_score": 10, "evidence_sections_present": 1}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_trend_snapshot",
                    "--evidence-pack",
                    str(evidence),
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


if __name__ == "__main__":
    unittest.main()
