import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationSelectionHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prev = root / "prev.json"
            curr = root / "curr.json"
            out = root / "summary.json"
            prev.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "latest_selected_large_ratio_pct": 45.0,
                        "latest_selected_families": 5,
                        "latest_selected_source_buckets": 3,
                        "latest_max_family_share_pct": 30.0,
                    }
                ),
                encoding="utf-8",
            )
            curr.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "latest_selected_large_ratio_pct": 35.0,
                        "latest_selected_families": 4,
                        "latest_selected_source_buckets": 2,
                        "latest_max_family_share_pct": 42.0,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_selection_history_trend_v1",
                    "--previous",
                    str(prev),
                    "--current",
                    str(curr),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")

    def test_trend_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_selection_history_trend_v1",
                    "--previous",
                    str(root / "missing_prev.json"),
                    "--current",
                    str(root / "missing_curr.json"),
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
