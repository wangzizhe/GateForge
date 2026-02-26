import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetAnchorReleaseBundleV3Tests(unittest.TestCase):
    def test_release_bundle_v3_scores_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            intake = root / "intake.json"
            validator = root / "validator.json"
            benchmark = root / "benchmark.json"
            compare = root / "compare.json"
            out = root / "summary.json"

            anchor.write_text(json.dumps({"anchor_ready": True, "anchor_pack_score": 80.0}), encoding="utf-8")
            intake.write_text(json.dumps({"accepted_count": 2}), encoding="utf-8")
            validator.write_text(json.dumps({"validated_count": 8, "expected_match_ratio_pct": 85.0}), encoding="utf-8")
            benchmark.write_text(json.dumps({"failure_type_drift": 0.2}), encoding="utf-8")
            compare.write_text(json.dumps({"verdict": "GATEFORGE_ADVANTAGE", "advantage_score": 7}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_release_bundle_v3",
                    "--anchor-benchmark-pack-v2-summary",
                    str(anchor),
                    "--open-source-intake-summary",
                    str(intake),
                    "--mutation-validator-summary",
                    str(validator),
                    "--failure-distribution-benchmark-v2-summary",
                    str(benchmark),
                    "--gateforge-vs-plain-ci-summary",
                    str(compare),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIsInstance(summary.get("release_score"), float)

    def test_release_bundle_v3_fails_on_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_release_bundle_v3",
                    "--anchor-benchmark-pack-v2-summary",
                    str(root / "missing1.json"),
                    "--open-source-intake-summary",
                    str(root / "missing2.json"),
                    "--mutation-validator-summary",
                    str(root / "missing3.json"),
                    "--failure-distribution-benchmark-v2-summary",
                    str(root / "missing4.json"),
                    "--gateforge-vs-plain-ci-summary",
                    str(root / "missing5.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
