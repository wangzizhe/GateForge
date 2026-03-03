import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationAuthenticScaleScoreV1Tests(unittest.TestCase):
    def test_score_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            exec_auth = root / "exec.json"
            failure_auth = root / "failure.json"
            depth = root / "depth.json"
            source = root / "source.json"
            out = root / "summary.json"
            exec_auth.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "solver_command_ratio_pct": 95.0,
                        "probe_only_command_ratio_pct": 2.0,
                        "failure_signal_ratio_pct": 70.0,
                    }
                ),
                encoding="utf-8",
            )
            failure_auth.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "failure_signal_ratio_pct": 68.0,
                        "expected_failure_type_signal_coverage_pct": 72.0,
                        "observed_coverage_ratio_pct": 80.0,
                    }
                ),
                encoding="utf-8",
            )
            depth.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "models_meeting_effective_depth_ratio_pct": 65.0,
                        "large_models_meeting_effective_depth_ratio_pct": 60.0,
                        "p10_effective_mutations_per_model": 2.0,
                    }
                ),
                encoding="utf-8",
            )
            source.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "existing_source_path_ratio_pct": 98.0,
                        "allowed_root_ratio_pct": 95.0,
                        "registry_match_ratio_pct": 92.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_authentic_scale_score_v1",
                    "--mutation-execution-authenticity-summary",
                    str(exec_auth),
                    "--mutation-failure-signal-authenticity-summary",
                    str(failure_auth),
                    "--mutation-effective-depth-summary",
                    str(depth),
                    "--mutation-source-provenance-summary",
                    str(source),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(float(payload.get("authentic_scale_score", 0.0)), 0.0)

    def test_score_fail_on_missing_required(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_authentic_scale_score_v1",
                    "--mutation-execution-authenticity-summary",
                    str(root / "missing_exec.json"),
                    "--mutation-failure-signal-authenticity-summary",
                    str(root / "missing_failure.json"),
                    "--mutation-effective-depth-summary",
                    str(root / "missing_depth.json"),
                    "--mutation-source-provenance-summary",
                    str(root / "missing_source.json"),
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
