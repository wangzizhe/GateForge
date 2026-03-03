import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationMilestoneEvidencePackV1Tests(unittest.TestCase):
    def test_milestone_evidence_pack_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bootstrap = root / "bootstrap.json"
            scale = root / "scale.json"
            gate = root / "gate.json"
            manifest = root / "manifest.json"
            out = root / "summary.json"

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
            manifest.write_text(json.dumps({"sources": [{"source_id": "a"}, {"source_id": "b"}]}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_milestone_evidence_pack_v1",
                    "--open-source-bootstrap-summary",
                    str(bootstrap),
                    "--scale-batch-summary",
                    str(scale),
                    "--scale-gate-summary",
                    str(gate),
                    "--source-manifest",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertTrue(payload.get("publishable"))
            self.assertGreaterEqual(float(payload.get("evidence_score", 0.0)), 80.0)
            self.assertGreaterEqual(len(payload.get("milestone_claims") or []), 3)

    def test_milestone_evidence_pack_fail_on_missing_required(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_milestone_evidence_pack_v1",
                    "--open-source-bootstrap-summary",
                    str(root / "missing_bootstrap.json"),
                    "--scale-batch-summary",
                    str(root / "missing_scale.json"),
                    "--scale-gate-summary",
                    str(root / "missing_gate.json"),
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
