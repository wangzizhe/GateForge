import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatEvidenceOnepagerV1Tests(unittest.TestCase):
    def test_onepager_builds_public_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            weekly = root / "weekly.json"
            history = root / "history.json"
            trend = root / "trend.json"
            runbook = root / "runbook.json"
            out = root / "summary.json"

            weekly.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "week_tag": "2026-W10",
                        "kpis": {
                            "real_model_count": 12,
                            "reproducible_mutation_count": 36,
                            "failure_distribution_stability_score": 90.0,
                            "gateforge_vs_plain_ci_advantage_score": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )
            history.write_text(json.dumps({"status": "PASS", "avg_stability_score": 89.0, "avg_advantage_score": 9.0}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "PASS", "trend": {"delta_avg_stability_score": 1.0}}), encoding="utf-8")
            runbook.write_text(json.dumps({"status": "PASS", "readiness": "READY", "repro_steps": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_evidence_onepager_v1",
                    "--moat-weekly-summary",
                    str(weekly),
                    "--moat-weekly-summary-history",
                    str(history),
                    "--moat-weekly-summary-history-trend",
                    str(trend),
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
            self.assertIsInstance((payload.get("public_metrics") or {}).get("real_model_count"), int)


if __name__ == "__main__":
    unittest.main()
