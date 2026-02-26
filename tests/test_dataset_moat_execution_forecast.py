import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatExecutionForecastTests(unittest.TestCase):
    def test_forecast_builds_three_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack = root / "pack.json"
            experiments = root / "experiments.json"
            moat = root / "moat.json"
            guard = root / "guard.json"
            out = root / "summary.json"

            pack.write_text(
                json.dumps(
                    {
                        "total_target_new_cases": 14,
                        "medium_target_new_cases": 5,
                        "large_target_new_cases": 3,
                    }
                ),
                encoding="utf-8",
            )
            experiments.write_text(
                json.dumps(
                    {
                        "recommended_experiment_id": "policy_exp.balanced",
                        "experiments": [
                            {"experiment_id": "policy_exp.balanced", "experiment_score": 70.0, "risk_score": 36.0},
                            {"experiment_id": "policy_exp.conservative", "experiment_score": 66.0, "risk_score": 30.0},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            moat.write_text(json.dumps({"metrics": {"moat_score": 60.0}}), encoding="utf-8")
            guard.write_text(json.dumps({"status": "PASS", "confidence_level": "high"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_execution_forecast",
                    "--modelica-failure-pack-planner",
                    str(pack),
                    "--policy-experiment-runner",
                    str(experiments),
                    "--moat-trend-snapshot",
                    str(moat),
                    "--replay-quality-guard",
                    str(guard),
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
            forecast = payload.get("forecast") if isinstance(payload.get("forecast"), list) else []
            self.assertEqual(len(forecast), 3)
            self.assertGreaterEqual(float(payload.get("projected_moat_score_30d", 0.0)), 0.0)

    def test_forecast_fails_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_execution_forecast",
                    "--modelica-failure-pack-planner",
                    str(root / "missing_pack.json"),
                    "--policy-experiment-runner",
                    str(root / "missing_exp.json"),
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
            self.assertIn("modelica_failure_pack_plan_missing", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
