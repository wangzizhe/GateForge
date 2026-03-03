import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelSourceDiversityHistoryLedgerV1Tests(unittest.TestCase):
    def test_source_diversity_history_ledger_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            guard = root / "guard.json"
            discovery = root / "discovery.json"
            runner = root / "runner.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"

            guard.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "unique_source_repos": 3,
                        "unique_source_buckets": 6,
                        "unique_source_buckets_for_large_models": 2,
                        "max_source_bucket_share_pct": 32.0,
                    }
                ),
                encoding="utf-8",
            )
            discovery.write_text(json.dumps({"total_candidates": 20}), encoding="utf-8")
            runner.write_text(json.dumps({"accepted_count": 12}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_source_diversity_history_ledger_v1",
                    "--source-diversity-guard-summary",
                    str(guard),
                    "--asset-discovery-summary",
                    str(discovery),
                    "--intake-runner-summary",
                    str(runner),
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
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(payload.get("total_records", 0)), 1)

    def test_source_diversity_history_ledger_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_source_diversity_history_ledger_v1",
                    "--source-diversity-guard-summary",
                    str(root / "missing_guard.json"),
                    "--asset-discovery-summary",
                    str(root / "missing_discovery.json"),
                    "--intake-runner-summary",
                    str(root / "missing_runner.json"),
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
