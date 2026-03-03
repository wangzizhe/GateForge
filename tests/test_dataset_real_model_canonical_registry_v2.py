import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelCanonicalRegistryV2Tests(unittest.TestCase):
    def test_canonical_registry_tracks_incremental_growth(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out_registry = root / "registry.json"
            out = root / "summary.json"

            previous.write_text(
                json.dumps(
                    {
                        "schema_version": "real_model_canonical_registry_v2",
                        "models": [
                            {
                                "canonical_id": "canon_old_1",
                                "latest_model_id": "m_old",
                                "latest_scale": "medium",
                                "first_seen_run_tag": "prev",
                                "last_seen_run_tag": "prev",
                                "seen_batches": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "schema_version": "real_model_executable_registry_rows_v1",
                        "models": [
                            {
                                "model_id": "m_old_variant",
                                "source_path": "a.mo",
                                "source_name": "s1",
                                "suggested_scale": "medium",
                                "checksum_sha256": "c1",
                                "structure_hash": "s1",
                            },
                            {
                                "model_id": "m_new_large",
                                "source_path": "b.mo",
                                "source_name": "s2",
                                "suggested_scale": "large",
                                "checksum_sha256": "c2",
                                "structure_hash": "s2",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_canonical_registry_v2",
                    "--current-executable-registry",
                    str(current),
                    "--previous-canonical-registry",
                    str(previous),
                    "--run-tag",
                    "run_001",
                    "--out-registry",
                    str(out_registry),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            registry = json.loads(out_registry.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(summary.get("current_unique_models", 0)), 2)
            self.assertEqual(int(summary.get("canonical_new_models", 0)), 2)
            self.assertEqual(int(summary.get("canonical_new_large_models", 0)), 1)
            self.assertEqual(int(summary.get("canonical_net_growth_models", 0)), 2)
            self.assertEqual(len(registry.get("models") or []), 3)

    def test_canonical_registry_fail_when_current_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_canonical_registry_v2",
                    "--current-executable-registry",
                    str(root / "missing_current.json"),
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
            self.assertIn("current_executable_registry_missing", summary.get("reasons") or [])


if __name__ == "__main__":
    unittest.main()
