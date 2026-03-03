import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetHardMoatTargetProfileV1Tests(unittest.TestCase):
    def test_target_profile_generates_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            profile = root / "profile.json"
            planner = root / "planner.json"
            canonical = root / "canonical.json"
            backfill = root / "backfill.json"
            out = root / "summary.json"
            target = root / "target.json"

            profile.write_text(
                json.dumps({"model_scale_profile": "large_first", "min_accepted_large_ratio_pct": 35.0}),
                encoding="utf-8",
            )
            planner.write_text(
                json.dumps({"status": "PASS", "planned_weekly_new_models": 20, "p0_channels": 0}),
                encoding="utf-8",
            )
            canonical.write_text(
                json.dumps({"status": "PASS", "canonical_total_models": 600, "canonical_net_growth_models": 8}),
                encoding="utf-8",
            )
            backfill.write_text(json.dumps({"status": "PASS", "p0_tasks": 0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_hard_moat_target_profile_v1",
                    "--profile-config",
                    str(profile),
                    "--ingest-source-channel-planner-summary",
                    str(planner),
                    "--canonical-registry-summary",
                    str(canonical),
                    "--coverage-backfill-summary",
                    str(backfill),
                    "--target-profile-out",
                    str(target),
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
            thresholds = payload.get("thresholds") if isinstance(payload.get("thresholds"), dict) else {}
            self.assertGreaterEqual(int(thresholds.get("min_generated_mutations", 0)), 40)
            self.assertEqual(payload.get("strictness_level"), "strict")
            self.assertTrue(target.exists())

    def test_target_profile_fail_when_profile_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_hard_moat_target_profile_v1",
                    "--profile-config",
                    str(root / "missing.json"),
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
