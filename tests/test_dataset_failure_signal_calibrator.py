import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureSignalCalibratorTests(unittest.TestCase):
    def test_calibrator_outputs_weights(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            b = root / "b.json"
            r = root / "r.json"
            out = root / "out.json"
            b.write_text(json.dumps({"distribution_drift_score": 0.2, "false_positive_rate_after": 0.03, "regression_rate_after": 0.05}), encoding="utf-8")
            r.write_text(json.dumps({"delta": {"detection_rate": 0.02}}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_failure_signal_calibrator", "--failure-distribution-benchmark", str(b), "--policy-patch-replay-evaluator", str(r), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIsInstance(payload.get("weights"), dict)

    def test_calibrator_fail_without_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_failure_signal_calibrator", "--failure-distribution-benchmark", str(Path(d) / "missing.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
