import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunPrivateModelMutationLargeFirstSprintV1Tests(unittest.TestCase):
    def test_run_largefirst_sprint_with_local_pool(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_largefirst_sprint_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_root = root / "private_pool"
            model_root.mkdir(parents=True, exist_ok=True)

            for idx in range(1, 4):
                (model_root / f"LargePlant{idx}.mo").write_text(
                    "\n".join(
                        [f"model LargePlant{idx}", "  Real x;", "  Real y;"]
                        + [f"  parameter Real p{i}={i};" for i in range(1, 170)]
                        + [
                            "equation",
                            "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
                            "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
                            f"end LargePlant{idx};",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
            (model_root / "MediumPlant.mo").write_text(
                "\n".join(
                    ["model MediumPlant", "  Real x;"]
                    + [f"  parameter Real k{i}={i};" for i in range(1, 90)]
                    + [
                        "equation",
                        "  der(x)=k1-k2+k3-k4+k5;",
                        "end MediumPlant;",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            out_dir = root / "largefirst_out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_PRIVATE_MODEL_ROOTS": str(model_root),
                    "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
                    "GATEFORGE_MIN_DISCOVERED_MODELS": "4",
                    "GATEFORGE_MIN_ACCEPTED_MODELS": "4",
                    "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "3",
                    "GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT": "70",
                    "GATEFORGE_MIN_GENERATED_MUTATIONS": "80",
                    "GATEFORGE_MIN_MUTATION_PER_MODEL": "6",
                    "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "60",
                },
                timeout=240,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("scale_gate_status"), "PASS")
            self.assertEqual(summary.get("model_scale_profile"), "large_first")
            self.assertGreaterEqual(float(summary.get("accepted_large_ratio_pct", 0.0)), 70.0)


if __name__ == "__main__":
    unittest.main()
