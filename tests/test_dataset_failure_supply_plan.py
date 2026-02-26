import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureSupplyPlanTests(unittest.TestCase):
    def test_supply_plan_outputs_targets(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            q = root / "q.json"
            p = root / "p.json"
            b = root / "b.json"
            out = root / "out.json"
            q.write_text(json.dumps({"total_queue_items": 3}), encoding="utf-8")
            p.write_text(json.dumps({"large_target_new_cases": 3, "medium_target_new_cases": 4}), encoding="utf-8")
            b.write_text(json.dumps({"campaign_phase": "scale_out"}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_failure_supply_plan", "--large-model-failure-queue", str(q), "--modelica-failure-pack-planner", str(p), "--large-model-campaign-board", str(b), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreater(int(payload.get("weekly_supply_target", 0)), 0)

    def test_supply_plan_fail_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_failure_supply_plan", "--large-model-failure-queue", str(Path(d) / "missing1.json"), "--modelica-failure-pack-planner", str(Path(d) / "missing2.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
