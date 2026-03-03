import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelAuthenticityGateV1Tests(unittest.TestCase):
    def test_gate_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            large_truth = root / "large_truth.json"
            depth = root / "depth.json"
            source = root / "source.json"
            out = root / "summary.json"
            large_truth.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "large_model_count": 12,
                        "large_executable_real_rate_pct": 82.0,
                    }
                ),
                encoding="utf-8",
            )
            depth.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "large_models_meeting_effective_depth_ratio_pct": 66.0,
                    }
                ),
                encoding="utf-8",
            )
            source.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "registry_match_ratio_pct": 94.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_authenticity_gate_v1",
                    "--large-model-executable-truth-summary",
                    str(large_truth),
                    "--mutation-effective-depth-summary",
                    str(depth),
                    "--mutation-source-provenance-summary",
                    str(source),
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
            self.assertGreaterEqual(float(payload.get("large_model_authenticity_score", 0.0)), 0.0)

    def test_gate_fail_when_no_large_models(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            large_truth = root / "large_truth.json"
            depth = root / "depth.json"
            source = root / "source.json"
            out = root / "summary.json"
            large_truth.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "large_model_count": 0,
                        "large_executable_real_rate_pct": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            depth.write_text(json.dumps({"status": "PASS", "large_models_meeting_effective_depth_ratio_pct": 0.0}), encoding="utf-8")
            source.write_text(json.dumps({"status": "PASS", "registry_match_ratio_pct": 90.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_authenticity_gate_v1",
                    "--large-model-executable-truth-summary",
                    str(large_truth),
                    "--mutation-effective-depth-summary",
                    str(depth),
                    "--mutation-source-provenance-summary",
                    str(source),
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
