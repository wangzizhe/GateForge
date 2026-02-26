import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelScaleMixGuardTests(unittest.TestCase):
    def test_mix_guard_outputs_ratios(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r = root / "r.json"
            out = root / "out.json"
            r.write_text(json.dumps({"model_scale_counts": {"small": 8, "medium": 4, "large": 2}}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_model_scale_mix_guard", "--failure-corpus-registry-summary", str(r), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIsInstance(payload.get("medium_ratio_pct"), float)

    def test_mix_guard_fail_missing_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_model_scale_mix_guard", "--failure-corpus-registry-summary", str(Path(d) / "missing.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
