import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationWeeklyFreezeManifestV1Tests(unittest.TestCase):
    def test_weekly_freeze_manifest_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            scale = root / "scale.json"
            canonical = root / "canonical.json"
            manifest = root / "mutation_manifest.json"
            validation = root / "validation.json"
            validation_v2 = root / "validation_v2.json"
            guard = root / "guard.json"
            freeze_manifest = root / "freeze_manifest.json"
            out = root / "summary.json"

            scale.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "accepted_models": 100,
                        "generated_mutations": 500,
                        "reproducible_mutations": 500,
                    }
                ),
                encoding="utf-8",
            )
            canonical.write_text(
                json.dumps({"status": "PASS", "canonical_net_growth_models": 5}),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps({"mutations": [{"mutation_id": "m1"}]}),
                encoding="utf-8",
            )
            validation.write_text(
                json.dumps({"status": "PASS", "baseline_check_pass_rate_pct": 100.0}),
                encoding="utf-8",
            )
            validation_v2.write_text(
                json.dumps({"status": "PASS", "overall": {"type_match_rate_pct": 60.0}}),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps({"status": "PASS"}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_weekly_freeze_manifest_v1",
                    "--week-tag",
                    "2026-W10",
                    "--scale-batch-summary",
                    str(scale),
                    "--canonical-registry-summary",
                    str(canonical),
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-validation-summary",
                    str(validation),
                    "--mutation-validation-matrix-v2-summary",
                    str(validation_v2),
                    "--failure-distribution-stability-guard-summary",
                    str(guard),
                    "--freeze-manifest-out",
                    str(freeze_manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            freeze_payload = json.loads(freeze_manifest.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertTrue(str(summary.get("freeze_id") or ""))
            self.assertEqual(freeze_payload.get("freeze_id"), summary.get("freeze_id"))

    def test_weekly_freeze_manifest_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_weekly_freeze_manifest_v1",
                    "--week-tag",
                    "2026-W10",
                    "--scale-batch-summary",
                    str(root / "missing_scale.json"),
                    "--canonical-registry-summary",
                    str(root / "missing_canonical.json"),
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--mutation-validation-summary",
                    str(root / "missing_validation.json"),
                    "--mutation-validation-matrix-v2-summary",
                    str(root / "missing_validation_v2.json"),
                    "--failure-distribution-stability-guard-summary",
                    str(root / "missing_guard.json"),
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
