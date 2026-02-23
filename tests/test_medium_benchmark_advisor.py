import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MediumBenchmarkAdvisorTests(unittest.TestCase):
    def _write_inputs(
        self,
        root: Path,
        latest_pass_rate: float,
        avg_pass_rate: float,
        mismatch_total: int,
        delta_pass_rate: float,
        history_alerts: list[str] | None = None,
        trend_alerts: list[str] | None = None,
    ) -> tuple[Path, Path]:
        history = root / "history_summary.json"
        trend = root / "history_trend.json"
        history.write_text(
            json.dumps(
                {
                    "latest_pass_rate": latest_pass_rate,
                    "avg_pass_rate": avg_pass_rate,
                    "mismatch_case_total": mismatch_total,
                    "alerts": history_alerts or [],
                }
            ),
            encoding="utf-8",
        )
        trend.write_text(
            json.dumps(
                {
                    "trend": {"delta_pass_rate": delta_pass_rate},
                    "trend_alerts": trend_alerts or [],
                }
            ),
            encoding="utf-8",
        )
        return history, trend

    def test_advisor_tightens_when_degrading(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history, trend = self._write_inputs(
                root,
                latest_pass_rate=0.75,
                avg_pass_rate=0.85,
                mismatch_total=2,
                delta_pass_rate=-0.2,
                history_alerts=["latest_pass_rate_low"],
                trend_alerts=["pass_rate_regression_detected"],
            )
            out = root / "advisor.json"
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_advisor",
                    "--history-summary",
                    str(history),
                    "--trend-summary",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("decision"), "TIGHTEN")
            self.assertEqual(advice.get("suggested_profile"), "industrial_strict_v0")
            self.assertTrue(advice.get("reasons"))

    def test_advisor_keeps_when_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history, trend = self._write_inputs(
                root,
                latest_pass_rate=1.0,
                avg_pass_rate=1.0,
                mismatch_total=0,
                delta_pass_rate=0.0,
            )
            out = root / "advisor.json"
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_advisor",
                    "--history-summary",
                    str(history),
                    "--trend-summary",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("decision"), "KEEP")
            self.assertEqual(advice.get("suggested_profile"), "default")
            self.assertEqual(advice.get("reasons"), [])


if __name__ == "__main__":
    unittest.main()
