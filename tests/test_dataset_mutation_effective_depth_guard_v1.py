import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationEffectiveDepthGuardV1Tests(unittest.TestCase):
    def test_guard_needs_review_when_depth_too_shallow(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "target_model_id": "mdl_a",
                                "target_scale": "large",
                                "expected_failure_type": "simulate_error",
                                "seed": 1,
                                "repro_command": "omc x.mos",
                            },
                            {
                                "mutation_id": "m2",
                                "target_model_id": "mdl_b",
                                "target_scale": "large",
                                "expected_failure_type": "simulate_error",
                                "seed": 2,
                                "repro_command": "python3 -c \"print('probe')\"",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            raw.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "execution_status": "EXECUTED", "final_return_code": 2, "attempts": [{"stderr": "failed"}]},
                            {"mutation_id": "m2", "execution_status": "EXECUTED", "final_return_code": 0, "attempts": [{"stderr": ""}]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_effective_depth_guard_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
                    "--min-models-meeting-threshold-ratio-pct",
                    "80",
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
            self.assertGreaterEqual(int(payload.get("tracked_models", 0)), 2)

    def test_guard_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_effective_depth_guard_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--mutation-raw-observations",
                    str(root / "missing_raw.json"),
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
