import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationSourceBucketEffectiveScaleV1Tests(unittest.TestCase):
    def test_source_bucket_effective_scale_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_a = root / "pool_a" / "plant" / "A.mo"
            model_b = root / "pool_b" / "drive" / "B.mo"
            model_a.parent.mkdir(parents=True, exist_ok=True)
            model_b.parent.mkdir(parents=True, exist_ok=True)
            model_a.write_text("model A\nend A;\n", encoding="utf-8")
            model_b.write_text("model B\nend B;\n", encoding="utf-8")

            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "source_model_path": str(model_a),
                                "target_model_id": "A",
                                "target_scale": "large",
                                "failure_type": "simulate_error",
                                "operator": "op",
                                "expected_stage": "simulate",
                                "seed": 1,
                                "repro_command": "omc run.mos",
                            },
                            {
                                "mutation_id": "m2",
                                "source_model_path": str(model_b),
                                "target_model_id": "B",
                                "target_scale": "medium",
                                "failure_type": "model_check_error",
                                "operator": "op",
                                "expected_stage": "check",
                                "seed": 2,
                                "repro_command": "omc run.mos",
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
                            {"mutation_id": "m1", "execution_status": "EXECUTED", "final_return_code": 1, "attempts": []},
                            {"mutation_id": "m2", "execution_status": "EXECUTED", "final_return_code": 1, "attempts": []},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_source_bucket_effective_scale_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
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
            self.assertGreaterEqual(int(payload.get("source_bucket_count", 0)), 1)
            self.assertGreaterEqual(int(payload.get("effective_mutations", 0)), 1)

    def test_source_bucket_effective_scale_fail_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_source_bucket_effective_scale_v1",
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
