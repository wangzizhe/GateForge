import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelFailureQueueTests(unittest.TestCase):
    def test_queue_prioritizes_large_items(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backlog = root / "backlog.json"
            registry = root / "registry.json"
            out = root / "summary.json"
            backlog.write_text(json.dumps({"tasks": [{"task_id": "blindspot.model_scale.large", "title": "large", "reason": "taxonomy_missing_model_scale", "priority": "P0"}]}), encoding="utf-8")
            registry.write_text(json.dumps({"missing_model_scales": ["large"]}), encoding="utf-8")
            proc = subprocess.run([
                sys.executable, "-m", "gateforge.dataset_large_model_failure_queue",
                "--blind-spot-backlog", str(backlog),
                "--failure-corpus-registry-summary", str(registry),
                "--out", str(out)
            ], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(payload.get("total_queue_items", 0)), 1)

    def test_queue_fail_without_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run([
                sys.executable, "-m", "gateforge.dataset_large_model_failure_queue",
                "--blind-spot-backlog", str(root / "missing.json"),
                "--out", str(out)
            ], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
