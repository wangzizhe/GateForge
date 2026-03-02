import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunPrivateModelMutationScaleSprintV1DemoTests(unittest.TestCase):
    def test_sprint_script_fails_without_private_models(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_scale_sprint_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "sprint_out"
            env = {
                **os.environ,
                "GATEFORGE_PRIVATE_MODEL_ROOTS": str(Path(d) / "missing_models"),
                "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
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
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
