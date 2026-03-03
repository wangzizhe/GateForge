import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelExecutableTruthGateV1Tests(unittest.TestCase):
    def test_truth_gate_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            records = root / "records.json"
            manifest = root / "manifest.json"
            observations = root / "observations.json"
            out = root / "summary.json"

            m1 = root / "models" / "Large1.mo"
            m2 = root / "models" / "Large2.mo"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m1", "asset_type": "model_source", "suggested_scale": "large", "source_path": str(m1)},
                            {"model_id": "m2", "asset_type": "model_source", "suggested_scale": "large", "source_path": str(m2)},
                            {"model_id": "m3", "asset_type": "model_source", "suggested_scale": "medium", "source_path": str(root / "models" / "M3.mo")},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            records.write_text(
                json.dumps(
                    {
                        "baseline_records": [
                            {"source_model_path": str(m1), "check_ok": True},
                            {"source_model_path": str(m2), "check_ok": True},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "mut_1", "target_model_id": "m1", "target_scale": "large"},
                            {"mutation_id": "mut_2", "target_model_id": "m2", "target_scale": "large"},
                            {"mutation_id": "mut_3", "target_model_id": "m3", "target_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            observations.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "mut_1", "execution_status": "EXECUTED", "final_return_code": 0},
                            {"mutation_id": "mut_2", "execution_status": "EXECUTED", "final_return_code": 0},
                            {"mutation_id": "mut_3", "execution_status": "EXECUTED", "final_return_code": 0},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_executable_truth_gate_v1",
                    "--executable-registry",
                    str(registry),
                    "--mutation-validation-records",
                    str(records),
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(observations),
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
            self.assertEqual(int(payload.get("large_model_count", 0)), 2)
            self.assertEqual(int(payload.get("large_executable_real_count", 0)), 2)

    def test_truth_gate_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_executable_truth_gate_v1",
                    "--executable-registry",
                    str(root / "missing_registry.json"),
                    "--mutation-validation-records",
                    str(root / "missing_records.json"),
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--mutation-raw-observations",
                    str(root / "missing_observations.json"),
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
