import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaWeeklyMetricsPageV1Tests(unittest.TestCase):
    def _run_page(self, baseline: Path, ledger: Path, out: Path, week_tag: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.agent_modelica_weekly_metrics_page_v1",
                "--baseline-summary",
                str(baseline),
                "--week-tag",
                week_tag,
                "--ledger",
                str(ledger),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_weekly_metrics_page_appends_history_and_computes_delta(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            ledger = root / "history.jsonl"
            out = root / "page.json"

            baseline.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "success_at_k_pct": 66.67,
                        "median_time_to_pass_sec": 75,
                        "median_repair_rounds": 2,
                        "regression_count": 1,
                        "physics_fail_count": 0,
                        "layered_pass_rate_pct_by_scale": {"small": 100.0, "medium": 50.0, "large": 50.0},
                        "top_fail_reasons": {"regression_fail": 1},
                        "top_fail_reasons_by_scale": {"medium": {"regression_fail": 1}},
                        "quota_mode": "target",
                        "coverage_gap": {"shortfall_total_tasks": 0},
                    }
                ),
                encoding="utf-8",
            )
            proc1 = self._run_page(baseline=baseline, ledger=ledger, out=out, week_tag="2026-W09")
            self.assertEqual(proc1.returncode, 0, msg=proc1.stderr or proc1.stdout)

            baseline.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "success_at_k_pct": 80.0,
                        "median_time_to_pass_sec": 60,
                        "median_repair_rounds": 2,
                        "regression_count": 0,
                        "physics_fail_count": 0,
                        "layered_pass_rate_pct_by_scale": {"small": 100.0, "medium": 100.0, "large": 50.0},
                        "top_fail_reasons": {},
                        "top_fail_reasons_by_scale": {"medium": {}},
                        "quota_mode": "adaptive",
                        "coverage_gap": {"shortfall_total_tasks": 8},
                    }
                ),
                encoding="utf-8",
            )
            proc2 = self._run_page(baseline=baseline, ledger=ledger, out=out, week_tag="2026-W10")
            self.assertEqual(proc2.returncode, 0, msg=proc2.stderr or proc2.stdout)

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("history_records"), 2)
            self.assertEqual(payload.get("quota_mode"), "adaptive")
            self.assertEqual(payload.get("coverage_gap_shortfall_total_tasks"), 8)
            delta = payload.get("delta_vs_previous") or {}
            self.assertEqual(delta.get("success_at_k_pct"), 13.33)
            self.assertEqual(delta.get("median_time_to_pass_sec"), -15.0)
            self.assertEqual(delta.get("regression_count"), -1.0)


if __name__ == "__main__":
    unittest.main()
