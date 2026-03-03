import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetJointMoatStrengthGateV1Tests(unittest.TestCase):
    def test_joint_gate_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            family = root / "family.json"
            source = root / "source.json"
            repro = root / "repro.json"
            large = root / "large.json"
            growth = root / "growth.json"
            hard = root / "hard.json"
            out = root / "summary.json"
            family.write_text(json.dumps({"status": "PASS", "family_entropy": 1.8}), encoding="utf-8")
            source.write_text(json.dumps({"status": "PASS", "max_source_bucket_share_pct": 35.0}), encoding="utf-8")
            repro.write_text(json.dumps({"status": "PASS", "models_meeting_depth_ratio_pct": 85.0}), encoding="utf-8")
            large.write_text(json.dumps({"status": "PASS", "large_executable_real_rate_pct": 82.0}), encoding="utf-8")
            growth.write_text(json.dumps({"status": "PASS", "true_growth_ratio_pct": 78.0}), encoding="utf-8")
            hard.write_text(json.dumps({"status": "PASS", "moat_hardness_score": 88.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_joint_moat_strength_gate_v1",
                    "--real-model-family-coverage-summary",
                    str(family),
                    "--real-model-source-diversity-summary",
                    str(source),
                    "--mutation-repro-depth-summary",
                    str(repro),
                    "--large-model-executable-truth-summary",
                    str(large),
                    "--real-model-net-growth-authenticity-summary",
                    str(growth),
                    "--hard-moat-gates-summary",
                    str(hard),
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
            self.assertGreaterEqual(float(payload.get("moat_strength_score", 0.0)), 0.0)

    def test_joint_gate_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_joint_moat_strength_gate_v1",
                    "--real-model-family-coverage-summary",
                    str(root / "missing_family.json"),
                    "--real-model-source-diversity-summary",
                    str(root / "missing_source.json"),
                    "--mutation-repro-depth-summary",
                    str(root / "missing_repro.json"),
                    "--large-model-executable-truth-summary",
                    str(root / "missing_large.json"),
                    "--real-model-net-growth-authenticity-summary",
                    str(root / "missing_growth.json"),
                    "--hard-moat-gates-summary",
                    str(root / "missing_hard.json"),
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
