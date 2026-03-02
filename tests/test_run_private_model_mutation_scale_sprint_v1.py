import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunPrivateModelMutationScaleSprintV1Tests(unittest.TestCase):
    def test_sprint_script_passes_with_sufficient_assets(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_scale_sprint_v1.sh"

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_dir = root / "private_models"
            model_dir.mkdir(parents=True, exist_ok=True)

            # 8 models with 2 large to satisfy sprint thresholds.
            for i in range(1, 7):
                (model_dir / f"Medium_{i}.mo").write_text(
                    "\n".join(
                        [
                            f"model Medium_{i}",
                            "  Real x;",
                        ]
                        + [f"  parameter Real k{j}={j};" for j in range(1, 95)]
                        + [
                            "equation",
                            "  der(x)=k1-k2+k3-k4+k5;",
                            f"end Medium_{i};",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
            for i in range(1, 3):
                (model_dir / f"Large_{i}.mo").write_text(
                    "\n".join(
                        [
                            f"model Large_{i}",
                            "  Real x;",
                            "  Real y;",
                            "  Real z;",
                        ]
                        + [f"  parameter Real p{j}={j};" for j in range(1, 190)]
                        + [
                            "equation",
                            "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
                            "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
                            "  der(z)=p15-p16+p17-p18+p19-p20+p21;",
                            f"end Large_{i};",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )

            out_dir = root / "sprint_out"
            env = {
                **os.environ,
                "GATEFORGE_PRIVATE_MODEL_ROOTS": str(model_dir),
                "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
                "GATEFORGE_MUTATION_TIMEOUT_SECONDS": "10",
                "GATEFORGE_MIN_DISCOVERED_MODELS": "8",
                "GATEFORGE_MIN_ACCEPTED_MODELS": "8",
                "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "2",
                "GATEFORGE_MIN_GENERATED_MUTATIONS": "80",
                "GATEFORGE_MIN_MUTATION_PER_MODEL": "6",
                "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "50",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=240,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("scale_gate_status"), "PASS")
            self.assertGreaterEqual(int(summary.get("generated_mutations", 0)), 80)


if __name__ == "__main__":
    unittest.main()
