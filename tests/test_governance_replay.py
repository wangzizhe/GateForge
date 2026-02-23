import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReplayTests(unittest.TestCase):
    def _prepare_source_summaries(self, root: Path) -> tuple[Path, Path]:
        snapshot = root / "snapshot.json"
        compare = root / "compare.json"
        apply = root / "apply.json"
        snapshot.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "risks": [],
                    "kpis": {
                        "recommended_profile": "default",
                        "strict_non_pass_rate": 0.0,
                        "strict_downgrade_rate": 0.0,
                        "review_recovery_rate": 1.0,
                        "fail_rate": 0.0,
                    },
                }
            ),
            encoding="utf-8",
        )
        compare_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.governance_promote_compare",
                "--snapshot",
                str(snapshot),
                "--profiles",
                "default",
                "industrial_strict",
                "--out",
                str(compare),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(compare_proc.returncode, 0, msg=compare_proc.stderr or compare_proc.stdout)
        apply_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.governance_promote_apply",
                "--compare-summary",
                str(compare),
                "--policy-profile",
                "default",
                "--require-ranking-explanation-structure",
                "--strict-ranking-explanation-structure",
                "--out",
                str(apply),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(apply_proc.returncode, 0, msg=apply_proc.stderr or apply_proc.stdout)
        return compare, apply

    def test_governance_replay_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare, apply = self._prepare_source_summaries(root)
            out = root / "replay.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay",
                    "--compare-summary",
                    str(compare),
                    "--apply-summary",
                    str(apply),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "PASS")
            self.assertEqual(payload.get("mismatches"), [])

    def test_governance_replay_needs_review_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare, apply = self._prepare_source_summaries(root)
            tampered_apply = root / "apply_tampered.json"
            payload = json.loads(apply.read_text(encoding="utf-8"))
            payload["policy_hash"] = "deadbeef"
            tampered_apply.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "replay.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay",
                    "--compare-summary",
                    str(compare),
                    "--apply-summary",
                    str(tampered_apply),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            replay = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(replay.get("decision"), "NEEDS_REVIEW")
            codes = [str(item.get("code")) for item in replay.get("mismatches", [])]
            self.assertIn("apply_policy_hash_mismatch", codes)

    def test_governance_replay_strict_fail_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare, apply = self._prepare_source_summaries(root)
            tampered_apply = root / "apply_tampered.json"
            payload = json.loads(apply.read_text(encoding="utf-8"))
            payload["policy_hash"] = "deadbeef"
            tampered_apply.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "replay.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay",
                    "--compare-summary",
                    str(compare),
                    "--apply-summary",
                    str(tampered_apply),
                    "--strict",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            replay = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(replay.get("decision"), "FAIL")

    def test_governance_replay_ignore_apply_key(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare, apply = self._prepare_source_summaries(root)
            tampered_apply = root / "apply_tampered.json"
            payload = json.loads(apply.read_text(encoding="utf-8"))
            payload["policy_hash"] = "deadbeef"
            tampered_apply.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out = root / "replay.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay",
                    "--compare-summary",
                    str(compare),
                    "--apply-summary",
                    str(tampered_apply),
                    "--ignore-apply-key",
                    "policy_hash",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            replay = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(replay.get("decision"), "PASS")
            self.assertEqual(replay.get("mismatches"), [])
            self.assertIn("policy_hash", replay.get("ignore_apply_keys", []))


if __name__ == "__main__":
    unittest.main()
