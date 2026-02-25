import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetStrategyAutotuneAdvisorTests(unittest.TestCase):
    def test_advisor_recommends_strict_when_signals_bad(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            governance = root / "governance.json"
            trend = root / "trend.json"
            effectiveness = root / "effectiveness.json"
            out = root / "advisor.json"
            governance.write_text(
                json.dumps(
                    {
                        "latest_status": "FAIL",
                        "total_records": 10,
                        "status_counts": {"PASS": 3, "NEEDS_REVIEW": 2, "FAIL": 5},
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["dataset_governance_fail_rate_increasing"]}}),
                encoding="utf-8",
            )
            effectiveness.write_text(
                json.dumps({"decision": "ROLLBACK_REVIEW"}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_strategy_autotune_advisor",
                    "--dataset-governance-summary",
                    str(governance),
                    "--dataset-governance-trend",
                    str(trend),
                    "--effectiveness-summary",
                    str(effectiveness),
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
            self.assertEqual(advice.get("suggested_policy_profile"), "dataset_strict")
            self.assertEqual(advice.get("suggested_action"), "tighten_generation_controls")

    def test_advisor_recommends_keep_when_signals_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            governance = root / "governance.json"
            trend = root / "trend.json"
            effectiveness = root / "effectiveness.json"
            out = root / "advisor.json"
            governance.write_text(
                json.dumps(
                    {
                        "latest_status": "PASS",
                        "total_records": 10,
                        "status_counts": {"PASS": 9, "NEEDS_REVIEW": 1, "FAIL": 0},
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"status": "PASS", "trend": {"alerts": []}}),
                encoding="utf-8",
            )
            effectiveness.write_text(
                json.dumps({"decision": "KEEP"}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_strategy_autotune_advisor",
                    "--dataset-governance-summary",
                    str(governance),
                    "--dataset-governance-trend",
                    str(trend),
                    "--effectiveness-summary",
                    str(effectiveness),
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
            self.assertEqual(advice.get("suggested_policy_profile"), "dataset_default")
            self.assertEqual(advice.get("suggested_action"), "keep")


if __name__ == "__main__":
    unittest.main()

