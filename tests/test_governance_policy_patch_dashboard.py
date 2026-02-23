import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyPatchDashboardTests(unittest.TestCase):
    def _write_inputs(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        proposal = root / "proposal.json"
        apply = root / "apply.json"
        history = root / "history.json"
        trend = root / "trend.json"
        rollback = root / "rollback.json"
        proposal.write_text(json.dumps({"proposal_id": "p-001"}), encoding="utf-8")
        apply.write_text(json.dumps({"final_status": "PASS"}), encoding="utf-8")
        history.write_text(json.dumps({"total_records": 3, "latest_status": "PASS"}), encoding="utf-8")
        trend.write_text(json.dumps({"trend": {"delta_total_records": 1, "delta_fail_rate": -0.2, "delta_reject_rate": -0.1}}), encoding="utf-8")
        rollback.write_text(
            json.dumps({"advice": {"decision": "KEEP", "rollback_recommended": False, "reasons": []}}), encoding="utf-8"
        )
        return proposal, apply, history, trend, rollback

    def test_dashboard_summary_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal, apply, history, trend, rollback = self._write_inputs(root)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_dashboard",
                    "--proposal",
                    str(proposal),
                    "--apply",
                    str(apply),
                    "--history",
                    str(history),
                    "--trend",
                    str(trend),
                    "--rollback",
                    str(rollback),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertEqual(payload.get("proposal_id"), "p-001")
            self.assertEqual(payload.get("rollback_decision"), "KEEP")
            self.assertEqual(payload.get("total_records"), 3)

    def test_dashboard_summary_fail_when_missing_proposal_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal, apply, history, trend, rollback = self._write_inputs(root)
            proposal.write_text(json.dumps({}), encoding="utf-8")
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_dashboard",
                    "--proposal",
                    str(proposal),
                    "--apply",
                    str(apply),
                    "--history",
                    str(history),
                    "--trend",
                    str(trend),
                    "--rollback",
                    str(rollback),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
