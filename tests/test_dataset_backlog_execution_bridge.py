import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetBacklogExecutionBridgeTests(unittest.TestCase):
    def test_bridge_generates_ready_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backlog = root / "backlog.json"
            out = root / "summary.json"
            backlog.write_text(
                json.dumps(
                    {
                        "total_open_tasks": 2,
                        "tasks": [
                            {
                                "task_id": "blindspot.model_scale.large",
                                "title": "Expand scale",
                                "reason": "taxonomy_missing_model_scale",
                                "priority": "P0",
                            },
                            {
                                "task_id": "blindspot.distribution_drift",
                                "title": "Rebalance",
                                "reason": "distribution_drift_exceeds_threshold",
                                "priority": "P1",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_backlog_execution_bridge",
                    "--backlog-summary",
                    str(backlog),
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
            self.assertEqual(payload.get("total_execution_tasks"), 2)
            self.assertEqual(payload.get("ready_count"), 2)

    def test_bridge_fail_on_invalid_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backlog = root / "backlog.json"
            out = root / "summary.json"
            backlog.write_text(json.dumps({"total_open_tasks": 0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_backlog_execution_bridge",
                    "--backlog-summary",
                    str(backlog),
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
