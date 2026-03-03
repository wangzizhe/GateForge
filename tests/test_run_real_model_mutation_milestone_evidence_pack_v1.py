import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunRealModelMutationMilestoneEvidencePackV1Tests(unittest.TestCase):
    def test_run_milestone_evidence_pack_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_real_model_mutation_milestone_evidence_pack_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bootstrap = root / "bootstrap.json"
            scale = root / "scale.json"
            gate = root / "scale_gate.json"
            manifest = root / "manifest.json"
            out_dir = root / "milestone_out"

            bootstrap.write_text(json.dumps({"status": "PASS", "harvest_total_candidates": 720, "accepted_models": 720}), encoding="utf-8")
            scale.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "scale_gate_status": "PASS",
                        "accepted_models": 606,
                        "accepted_large_models": 153,
                        "generated_mutations": 3780,
                        "reproducible_mutations": 3780,
                        "selected_mutation_models": 378,
                        "failure_types_count": 5,
                        "mutations_per_failure_type": 2,
                    }
                ),
                encoding="utf-8",
            )
            gate.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            manifest.write_text(json.dumps({"sources": [{"source_id": "a"}]}), encoding="utf-8")

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_REAL_MODEL_MUTATION_MILESTONE_OUT_DIR": str(out_dir),
                    "GATEFORGE_MODELICA_BOOTSTRAP_SUMMARY": str(bootstrap),
                    "GATEFORGE_SCALE_BATCH_SUMMARY": str(scale),
                    "GATEFORGE_SCALE_GATE_SUMMARY": str(gate),
                    "GATEFORGE_MODELICA_SOURCE_MANIFEST": str(manifest),
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(payload.get("accepted_models", 0) or 0), 1)


if __name__ == "__main__":
    unittest.main()
