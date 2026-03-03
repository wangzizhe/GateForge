import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunRealModelMutationCoverageQualityGateV1Tests(unittest.TestCase):
    def test_run_coverage_quality_gate_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_real_model_mutation_coverage_quality_gate_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            scale_dir = root / "scale"
            scale_dir.mkdir(parents=True, exist_ok=True)
            (scale_dir / "summary.json").write_text(json.dumps({"scale_gate_status": "PASS"}), encoding="utf-8")
            (scale_dir / "intake_registry_rows.json").write_text(
                json.dumps({"models": [{"model_id": "m1", "suggested_scale": "medium"}, {"model_id": "m2", "suggested_scale": "large"}]}),
                encoding="utf-8",
            )
            muts = []
            obs = []
            i = 0
            for model in ["m1", "m2"]:
                for ft in ["simulate_error", "model_check_error", "semantic_regression", "numerical_instability", "constraint_violation"]:
                    i += 1
                    mid = f"x{i}"
                    muts.append({"mutation_id": mid, "target_model_id": model, "expected_failure_type": ft})
                    obs.append({"mutation_id": mid, "execution_status": "EXECUTED"})
            (scale_dir / "mutation_manifest.json").write_text(json.dumps({"mutations": muts}), encoding="utf-8")
            (scale_dir / "mutation_raw_observations.json").write_text(json.dumps({"observations": obs}), encoding="utf-8")

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
                    "GATEFORGE_COVERAGE_GATE_OUT_DIR": str(out_dir),
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")


if __name__ == "__main__":
    unittest.main()
