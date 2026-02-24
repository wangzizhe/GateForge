import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MVPFreezeTests(unittest.TestCase):
    def _write_artifacts(
        self, root: Path, matrix_status: str = "PASS"
    ) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
        medium = root / "medium.json"
        mutation = root / "mutation.json"
        autotune = root / "policy_autotune.json"
        autotune_gov = root / "policy_autotune_governance.json"
        autotune_gov_advisor_history = root / "policy_autotune_governance_advisor_history.json"
        policy = root / "policy.json"
        matrix = root / "matrix.json"
        medium.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        mutation.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        autotune.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        autotune_gov.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        autotune_gov_advisor_history.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        policy.write_text(json.dumps({"bundle_status": "PASS"}), encoding="utf-8")
        matrix.write_text(json.dumps({"matrix_status": matrix_status}), encoding="utf-8")
        return medium, mutation, autotune, autotune_gov, autotune_gov_advisor_history, policy, matrix

    def test_mvp_freeze_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            medium, mutation, autotune, autotune_gov, autotune_gov_advisor_history, policy, matrix = self._write_artifacts(root)
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
                    "--policy-autotune-rc",
                    "0",
                    "--policy-autotune-governance-rc",
                    "0",
                    "--policy-autotune-governance-advisor-history-rc",
                    "0",
                    "--policy-dashboard-rc",
                    "0",
                    "--ci-matrix-rc",
                    "0",
                    "--medium-dashboard-json",
                    str(medium),
                    "--mutation-dashboard-json",
                    str(mutation),
                    "--policy-autotune-json",
                    str(autotune),
                    "--policy-autotune-governance-json",
                    str(autotune_gov),
                    "--policy-autotune-governance-advisor-history-json",
                    str(autotune_gov_advisor_history),
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
            medium, mutation, autotune, autotune_gov, autotune_gov_advisor_history, policy, matrix = self._write_artifacts(
                root, matrix_status="FAIL"
            )
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
                    "--policy-autotune-rc",
                    "0",
                    "--policy-autotune-governance-rc",
                    "0",
                    "--policy-autotune-governance-advisor-history-rc",
                    "0",
                    "--policy-dashboard-rc",
                    "0",
                    "--ci-matrix-rc",
                    "1",
                    "--medium-dashboard-json",
                    str(medium),
                    "--mutation-dashboard-json",
                    str(mutation),
                    "--policy-autotune-json",
                    str(autotune),
                    "--policy-autotune-governance-json",
                    str(autotune_gov),
                    "--policy-autotune-governance-advisor-history-json",
                    str(autotune_gov_advisor_history),
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
