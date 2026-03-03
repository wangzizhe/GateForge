import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelPoolAuditV1Tests(unittest.TestCase):
    def test_pool_audit_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_dir = root / "models"
            model_dir.mkdir(parents=True, exist_ok=True)
            model_a = model_dir / "A.mo"
            model_a.write_text("model A\n  Real x;\n" + "\n".join([f"  parameter Real p{i}={i};" for i in range(1, 50)]) + "\nend A;\n", encoding="utf-8")

            registry = root / "registry.json"
            accepted = root / "accepted.json"
            out = root / "summary.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"asset_type": "model_source", "source_path": str(model_a), "suggested_scale": "large"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            accepted.write_text(json.dumps({"rows": [{"candidate_id": "A"}]}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_pool_audit_v1",
                    "--executable-registry",
                    str(registry),
                    "--intake-runner-accepted",
                    str(accepted),
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
            self.assertEqual(int(payload.get("missing_model_files", 0)), 0)

    def test_pool_audit_fail_when_missing_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_pool_audit_v1",
                    "--executable-registry",
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
