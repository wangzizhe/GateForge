import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaLayeredBaselineV1Tests(unittest.TestCase):
    def test_layered_baseline_summary_contains_required_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "mutation_manifest.json"
            out_dir = root / "out"
            summary = root / "summary.json"

            rows = []
            idx = 0
            for scale in ["small", "medium", "large"]:
                for ftype in ["model_check_error", "simulate_error", "semantic_regression"]:
                    idx += 1
                    rows.append(
                        {
                            "mutation_id": f"m{idx}",
                            "target_scale": scale,
                            "expected_failure_type": ftype,
                            "source_model_path": f"{scale}_{ftype}.mo",
                            "mutated_model_path": f"{scale}_{ftype}_mut.mo",
                        }
                    )

            manifest.write_text(json.dumps({"mutations": rows}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_layered_baseline_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                    "--max-per-scale",
                    "3",
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(payload.get("total_tasks"), 9)
            self.assertIn("success_at_k_pct", payload)
            self.assertIn("median_time_to_pass_sec", payload)
            self.assertIn("median_repair_rounds", payload)
            self.assertIn("regression_count", payload)
            self.assertIn("physics_fail_count", payload)
            layered = payload.get("layered_pass_rate_pct_by_scale") or {}
            self.assertEqual(set(layered.keys()), {"small", "medium", "large"})


if __name__ == "__main__":
    unittest.main()
