import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationCoverageQualityGateV1Tests(unittest.TestCase):
    def test_coverage_gate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m_med", "suggested_scale": "medium"},
                            {"model_id": "m_lrg", "suggested_scale": "large"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            mutations = []
            obs = []
            idx = 1
            for scale_model in ["m_med", "m_lrg"]:
                for ft in [
                    "simulate_error",
                    "model_check_error",
                    "semantic_regression",
                    "numerical_instability",
                    "constraint_violation",
                ]:
                    mid = f"m{idx}"
                    mutations.append({"mutation_id": mid, "target_model_id": scale_model, "expected_failure_type": ft})
                    obs.append({"mutation_id": mid, "execution_status": "EXECUTED"})
                    idx += 1
            manifest.write_text(json.dumps({"mutations": mutations}), encoding="utf-8")
            raw.write_text(json.dumps({"observations": obs}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_coverage_quality_gate_v1",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
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
            self.assertEqual(payload.get("required_cell_count"), payload.get("covered_required_cell_count"))

    def test_coverage_gate_needs_review_when_missing_cells(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps({"models": [{"model_id": "m_med", "suggested_scale": "medium"}]}),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "a1", "target_model_id": "m_med", "expected_failure_type": "simulate_error"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            raw.write_text(json.dumps({"observations": [{"mutation_id": "a1", "execution_status": "EXECUTED"}]}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_coverage_quality_gate_v1",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("required_cells_missing", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
