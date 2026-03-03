import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationEffectiveScaleGuardV1Tests(unittest.TestCase):
    def test_guard_needs_review_when_effective_scale_too_low(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack = root / "pack.json"
            realrun = root / "realrun.json"
            signature = root / "signature.json"
            exec_auth = root / "exec_auth.json"
            failure_auth = root / "failure_auth.json"
            out = root / "summary.json"
            pack.write_text(json.dumps({"total_mutations": 100}), encoding="utf-8")
            realrun.write_text(json.dumps({"executed_count": 100}), encoding="utf-8")
            signature.write_text(json.dumps({"unique_signature_ratio_pct": 100.0}), encoding="utf-8")
            exec_auth.write_text(json.dumps({"solver_command_ratio_pct": 1.0}), encoding="utf-8")
            failure_auth.write_text(json.dumps({"failure_signal_ratio_pct": 1.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_effective_scale_guard_v1",
                    "--mutation-pack-summary",
                    str(pack),
                    "--mutation-real-runner-summary",
                    str(realrun),
                    "--mutation-signature-uniqueness-summary",
                    str(signature),
                    "--mutation-execution-authenticity-summary",
                    str(exec_auth),
                    "--mutation-failure-signal-authenticity-summary",
                    str(failure_auth),
                    "--min-authenticity-multiplier",
                    "0.1",
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
            self.assertLess(float(payload.get("authenticity_multiplier", 1.0)), 0.1)

    def test_guard_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_effective_scale_guard_v1",
                    "--mutation-pack-summary",
                    str(root / "missing_pack.json"),
                    "--mutation-real-runner-summary",
                    str(root / "missing_realrun.json"),
                    "--mutation-signature-uniqueness-summary",
                    str(root / "missing_signature.json"),
                    "--mutation-execution-authenticity-summary",
                    str(root / "missing_exec_auth.json"),
                    "--mutation-failure-signal-authenticity-summary",
                    str(root / "missing_failure_auth.json"),
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
