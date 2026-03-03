import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationWeeklyFreezeDiffV1Tests(unittest.TestCase):
    def test_freeze_diff_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"

            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "accepted_models": 100,
                        "generated_mutations": 500,
                        "reproducible_mutations": 500,
                        "canonical_net_growth_models": 10,
                        "validation_type_match_rate_pct": 70.0,
                        "sources": {"checksums_sha256": {"a": "1"}},
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "accepted_models": 95,
                        "generated_mutations": 480,
                        "reproducible_mutations": 470,
                        "canonical_net_growth_models": 5,
                        "validation_type_match_rate_pct": 65.0,
                        "sources": {"checksums_sha256": {"a": "2"}},
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_weekly_freeze_diff_v1",
                    "--current-freeze-summary",
                    str(current),
                    "--previous-freeze-summary",
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
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("freeze_status_worsened", payload.get("alerts") or [])

    def test_freeze_diff_fail_on_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_weekly_freeze_diff_v1",
                    "--current-freeze-summary",
                    str(root / "missing_current.json"),
                    "--previous-freeze-summary",
                    str(root / "missing_previous.json"),
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
