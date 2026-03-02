import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunPrivateModelMutationScaleBatchV1Tests(unittest.TestCase):
    def test_run_private_batch_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_scale_batch_v1.sh"

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_dir = root / "private_models"
            model_dir.mkdir(parents=True, exist_ok=True)

            (model_dir / "MediumA.mo").write_text(
                "\n".join(
                    [
                        "model MediumA",
                        "  Real x;",
                    ]
                    + [f"  parameter Real k{i}={i};" for i in range(1, 90)]
                    + [
                        "equation",
                        "  der(x)=k1-k2+k3-k4+k5;",
                        "end MediumA;",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (model_dir / "LargeA.mo").write_text(
                "\n".join(
                    [
                        "model LargeA",
                        "  Real x;",
                        "  Real y;",
                    ]
                    + [f"  parameter Real p{i}={i};" for i in range(1, 180)]
                    + [
                        "equation",
                        "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
                        "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
                        "end LargeA;",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            out_dir = root / "batch_out"
            env = {
                **os.environ,
                "GATEFORGE_PRIVATE_MODEL_ROOTS": str(model_dir),
                "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
                "GATEFORGE_MIN_DISCOVERED_MODELS": "2",
                "GATEFORGE_MIN_ACCEPTED_MODELS": "2",
                "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "1",
                "GATEFORGE_MIN_GENERATED_MUTATIONS": "20",
                "GATEFORGE_MIN_MUTATION_PER_MODEL": "6",
                "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "10",
            }

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("bundle_status"), "PASS")
            self.assertGreaterEqual(int(summary.get("accepted_models", 0)), 2)
            self.assertGreaterEqual(int(summary.get("generated_mutations", 0)), 20)


if __name__ == "__main__":
    unittest.main()
