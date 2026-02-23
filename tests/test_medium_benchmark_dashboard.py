import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MediumBenchmarkDashboardTests(unittest.TestCase):
    def _write_inputs(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        summary = root / "summary.json"
        analysis = root / "analysis.json"
        history = root / "history.json"
        trend = root / "trend.json"
        advisor = root / "advisor.json"

        summary.write_text(
            json.dumps({"pack_id": "medium_pack_v1", "pass_rate": 1.0, "mismatch_case_count": 0}),
            encoding="utf-8",
        )
        analysis.write_text(
            json.dumps({"mismatch_case_count": 0, "recommendations": []}),
            encoding="utf-8",
        )
        history.write_text(
            json.dumps({"total_records": 2, "latest_pass_rate": 1.0, "avg_pass_rate": 1.0}),
            encoding="utf-8",
        )
        trend.write_text(
            json.dumps({"trend": {"delta_pass_rate": 0.0, "delta_mismatch_case_total": 0}}),
            encoding="utf-8",
        )
        advisor.write_text(
            json.dumps({"advice": {"decision": "KEEP", "suggested_profile": "default", "reasons": []}}),
            encoding="utf-8",
        )
        return summary, analysis, history, trend, advisor

    def test_dashboard_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary, analysis, history, trend, advisor = self._write_inputs(root)
            out = root / "dashboard.json"
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_dashboard",
                    "--summary",
                    str(summary),
                    "--analysis",
                    str(analysis),
                    "--history",
                    str(history),
                    "--trend",
                    str(trend),
                    "--advisor",
                    str(advisor),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertEqual(payload.get("pack_id"), "medium_pack_v1")
            self.assertEqual(payload.get("advisor_decision"), "KEEP")

    def test_dashboard_fail_when_missing_required_field(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary, analysis, history, trend, advisor = self._write_inputs(root)
            summary.write_text(json.dumps({}), encoding="utf-8")
            out = root / "dashboard.json"
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_dashboard",
                    "--summary",
                    str(summary),
                    "--analysis",
                    str(analysis),
                    "--history",
                    str(history),
                    "--trend",
                    str(trend),
                    "--advisor",
                    str(advisor),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
