import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunRealModelUniquenessGuardV1Tests(unittest.TestCase):
    def test_run_uniqueness_guard_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_real_model_uniqueness_guard_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            scale_dir = root / "scale"
            scale_dir.mkdir(parents=True, exist_ok=True)
            (scale_dir / "summary.json").write_text(json.dumps({"scale_gate_status": "PASS"}), encoding="utf-8")
            (scale_dir / "m1.mo").write_text("model M1\n Real x;\nequation\n der(x)= -x;\nend M1;\n", encoding="utf-8")
            (scale_dir / "m2.mo").write_text("model M2\n Real y;\nequation\n der(y)= -0.2*y;\nend M2;\n", encoding="utf-8")
            (scale_dir / "intake_runner_accepted.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {"candidate_id": "m1", "model_path": str(scale_dir / "m1.mo"), "source_url": "https://x/m1", "expected_scale": "large"},
                            {"candidate_id": "m2", "model_path": str(scale_dir / "m2.mo"), "source_url": "https://x/m2", "expected_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (scale_dir / "intake_registry_rows.json").write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m1", "asset_type": "model_source", "source_path": str(scale_dir / "m1.mo")},
                            {"model_id": "m2", "asset_type": "model_source", "source_path": str(scale_dir / "m2.mo")},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_SCALE_BATCH_SUMMARY": str(scale_dir / "summary.json"),
                    "GATEFORGE_REAL_MODEL_UNIQUENESS_OUT_DIR": str(out_dir),
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(payload.get("accepted_count", 0) or 0), 2)


if __name__ == "__main__":
    unittest.main()
