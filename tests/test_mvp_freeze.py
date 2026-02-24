import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MVPFreezeTests(unittest.TestCase):
    def _write_artifacts(self, root: Path, matrix_status: str = "PASS") -> tuple[Path, Path, Path, Path]:
        medium = root / "medium.json"
        mutation = root / "mutation.json"
        policy = root / "policy.json"
        matrix = root / "matrix.json"
        medium.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        mutation.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        policy.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        matrix.write_text(json.dumps({"matrix_status": matrix_status}), encoding="utf-8")
        return medium, mutation, policy, matrix

    def test_mvp_freeze_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            medium, mutation, policy, matrix = self._write_artifacts(root)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.mvp_freeze",
                    "--tests-rc",
                    "0",
                    "--medium-dashboard-rc",
                    "0",
                    "--mutation-dashboard-rc",
                    "0",
                    "--policy-dashboard-rc",
                    "0",
                    "--ci-matrix-rc",
                    "0",
                    "--medium-dashboard-json",
                    str(medium),
                    "--mutation-dashboard-json",
                    str(mutation),
                    "--policy-dashboard-json",
                    str(policy),
                    "--ci-matrix-json",
                    str(matrix),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("verdict"), "MVP_FREEZE_PASS")
            self.assertIsNone(payload.get("blocking_step"))

    def test_mvp_freeze_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            medium, mutation, policy, matrix = self._write_artifacts(root, matrix_status="FAIL")
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.mvp_freeze",
                    "--tests-rc",
                    "0",
                    "--medium-dashboard-rc",
                    "0",
                    "--mutation-dashboard-rc",
                    "0",
                    "--policy-dashboard-rc",
                    "0",
                    "--ci-matrix-rc",
                    "1",
                    "--medium-dashboard-json",
                    str(medium),
                    "--mutation-dashboard-json",
                    str(mutation),
                    "--policy-dashboard-json",
                    str(policy),
                    "--ci-matrix-json",
                    str(matrix),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("verdict"), "MVP_FREEZE_FAIL")
            self.assertEqual(payload.get("blocking_step"), "ci_matrix_targeted")


if __name__ == "__main__":
    unittest.main()
