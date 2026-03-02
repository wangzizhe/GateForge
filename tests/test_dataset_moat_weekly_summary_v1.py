import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatWeeklySummaryV1Tests(unittest.TestCase):
    def test_weekly_summary_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            scorecard = root / "scorecard.json"
            inventory = root / "inventory.json"
            freeze = root / "freeze.json"
            runbook = root / "runbook.json"
            out = root / "summary.json"

            scorecard.write_text(
                json.dumps(
                    {
                        "baseline_id": "moat-baseline-test",
                        "indicators": {
                            "real_model_count": 12,
                            "reproducible_mutation_count": 36,
                            "failure_type_coverage_score": 92.0,
                            "failure_distribution_stability_score": 90.0,
                            "gateforge_vs_plain_ci_advantage_score": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )
            inventory.write_text(json.dumps({"total_models": 12, "by_scale": {"small": 6, "medium": 4, "large": 2}}), encoding="utf-8")
            freeze.write_text(json.dumps({"freeze_id": "failure-freeze-test"}), encoding="utf-8")
            runbook.write_text(json.dumps({"readiness": "READY"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_weekly_summary_v1",
                    "--week-tag",
                    "2026-W10",
                    "--moat-scorecard-baseline-summary",
                    str(scorecard),
                    "--model-asset-inventory-report-summary",
                    str(inventory),
                    "--failure-distribution-baseline-freeze-summary",
                    str(freeze),
                    "--moat-repro-runbook-summary",
                    str(runbook),
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
            self.assertEqual(payload.get("week_tag"), "2026-W10")

    def test_weekly_summary_fails_when_required_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_weekly_summary_v1",
                    "--week-tag",
                    "2026-W10",
                    "--moat-scorecard-baseline-summary",
                    str(root / "missing1.json"),
                    "--model-asset-inventory-report-summary",
                    str(root / "missing2.json"),
                    "--failure-distribution-baseline-freeze-summary",
                    str(root / "missing3.json"),
                    "--moat-repro-runbook-summary",
                    str(root / "missing4.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
