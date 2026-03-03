import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelUniquenessGuardV1Tests(unittest.TestCase):
    def test_uniqueness_guard_detects_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m1 = root / "m1.mo"
            m1_copy = root / "m1_copy.mo"
            m2 = root / "m2.mo"
            m1.write_text("model M1\n Real x;\nequation\n der(x)= -x;\nend M1;\n", encoding="utf-8")
            m1_copy.write_text(m1.read_text(encoding="utf-8"), encoding="utf-8")
            m2.write_text("model M2\n Real y;\nequation\n der(y)= -0.2*y;\nend M2;\n", encoding="utf-8")

            accepted = root / "accepted.json"
            accepted.write_text(
                json.dumps(
                    {
                        "rows": [
                            {"candidate_id": "m1", "model_path": str(m1), "source_url": "https://x/m1", "expected_scale": "large"},
                            {"candidate_id": "m1c", "model_path": str(m1_copy), "source_url": "https://x/m1c", "expected_scale": "large"},
                            {"candidate_id": "m2", "model_path": str(m2), "source_url": "https://x/m2", "expected_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m1", "asset_type": "model_source", "source_path": str(m1)},
                            {"model_id": "m1c", "asset_type": "model_source", "source_path": str(m1_copy)},
                            {"model_id": "m2", "asset_type": "model_source", "source_path": str(m2)},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_uniqueness_guard_v1",
                    "--intake-runner-accepted",
                    str(accepted),
                    "--intake-registry-rows",
                    str(registry),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("accepted_count"), 3)
            self.assertEqual(payload.get("unique_checksum_count"), 2)
            self.assertGreaterEqual(float(payload.get("duplicate_ratio_pct", 0.0)), 30.0)

    def test_uniqueness_guard_fail_when_accepted_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_uniqueness_guard_v1",
                    "--intake-runner-accepted",
                    str(Path(d) / "missing.json"),
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
