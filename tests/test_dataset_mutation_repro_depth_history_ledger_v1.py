import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationReproDepthHistoryLedgerV1Tests(unittest.TestCase):
    def test_repro_depth_history_ledger_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            guard = root / "guard.json"
            pack = root / "pack.json"
            realrun = root / "realrun.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"

            guard.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "tracked_models": 12,
                        "models_meeting_depth_threshold": 10,
                        "models_meeting_depth_ratio_pct": 83.33,
                        "p10_reproducible_mutations_per_model": 6.0,
                        "max_model_share_pct": 22.0,
                    }
                ),
                encoding="utf-8",
            )
            pack.write_text(json.dumps({"total_mutations": 120}), encoding="utf-8")
            realrun.write_text(json.dumps({"executed_count": 110}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_repro_depth_history_ledger_v1",
                    "--mutation-repro-depth-guard-summary",
                    str(guard),
                    "--mutation-pack-summary",
                    str(pack),
                    "--mutation-real-runner-summary",
                    str(realrun),
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

    def test_repro_depth_history_ledger_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_repro_depth_history_ledger_v1",
                    "--mutation-repro-depth-guard-summary",
                    str(root / "missing_guard.json"),
                    "--mutation-pack-summary",
                    str(root / "missing_pack.json"),
                    "--mutation-real-runner-summary",
                    str(root / "missing_realrun.json"),
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
