import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelNetGrowthAuthenticityGateV1Tests(unittest.TestCase):
    def test_gate_detects_suspicious_new_models(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary = root / "canonical_summary.json"
            registry = root / "canonical_registry.json"
            out = root / "summary.json"
            summary.write_text(json.dumps({"run_tag": "run_b", "canonical_new_models": 2}), encoding="utf-8")
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "canonical_id": "old_1",
                                "first_seen_run_tag": "run_a",
                                "structure_hash": "s_old",
                                "checksum_sha256": "c_old",
                                "latest_scale": "large",
                            },
                            {
                                "canonical_id": "new_1",
                                "first_seen_run_tag": "run_b",
                                "structure_hash": "s_old",
                                "checksum_sha256": "c_new1",
                                "latest_scale": "large",
                            },
                            {
                                "canonical_id": "new_2",
                                "first_seen_run_tag": "run_b",
                                "structure_hash": "s_new2",
                                "checksum_sha256": "c_new2",
                                "latest_scale": "medium",
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
                    "gateforge.dataset_real_model_net_growth_authenticity_gate_v1",
                    "--canonical-registry-summary",
                    str(summary),
                    "--canonical-registry",
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
            self.assertEqual(int(payload.get("canonical_new_models", 0)), 2)
            self.assertEqual(int(payload.get("net_new_unique_models", 0)), 1)
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})

    def test_gate_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_net_growth_authenticity_gate_v1",
                    "--canonical-registry-summary",
                    str(root / "missing_summary.json"),
                    "--canonical-registry",
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
