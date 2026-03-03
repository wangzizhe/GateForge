import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelSourceDiversityGuardV1Tests(unittest.TestCase):
    def test_source_diversity_guard_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            out = root / "summary.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "m1",
                                "asset_type": "model_source",
                                "source_repo": "repo_a",
                                "source_path": str(root / "repo_a" / "fluid" / "m1.mo"),
                                "suggested_scale": "large",
                            },
                            {
                                "model_id": "m2",
                                "asset_type": "model_source",
                                "source_repo": "repo_b",
                                "source_path": str(root / "repo_b" / "thermal" / "m2.mo"),
                                "suggested_scale": "medium",
                            },
                            {
                                "model_id": "m3",
                                "asset_type": "model_source",
                                "source_repo": "repo_c",
                                "source_path": str(root / "repo_c" / "mechanical" / "m3.mo"),
                                "suggested_scale": "large",
                            },
                            {
                                "model_id": "m4",
                                "asset_type": "model_source",
                                "source_repo": "repo_a",
                                "source_path": str(root / "repo_a" / "control" / "m4.mo"),
                                "suggested_scale": "medium",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_source_diversity_guard_v1",
                    "--executable-registry",
                    str(registry),
                    "--min-source-repos",
                    "2",
                    "--min-source-buckets",
                    "3",
                    "--min-source-buckets-for-large-models",
                    "1",
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
            self.assertEqual(int(payload.get("total_models", 0)), 4)

    def test_source_diversity_guard_fail_when_missing_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_source_diversity_guard_v1",
                    "--executable-registry",
                    str(root / "missing_registry.json"),
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
