import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePromoteCompareTests(unittest.TestCase):
    def test_promote_compare_selects_best_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "summary.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": [],
                        "kpis": {
                            "recommended_profile": "default",
                            "strict_non_pass_rate": 0.0,
                            "strict_downgrade_rate": 0.0,
                            "review_recovery_rate": 0.9,
                            "fail_rate": 0.1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
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
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("best_profile"), "default")
            self.assertIn(
                payload.get("best_reason"),
                {"recommended_profile_preferred_within_top_total_score", "highest_total_score"},
            )
            self.assertIsInstance(payload.get("best_total_score"), int)
            self.assertIsInstance(payload.get("best_score_breakdown"), dict)
            self.assertIsInstance(payload.get("ranking"), list)
            self.assertEqual(payload.get("ranking", [])[0].get("rank"), 1)

    def test_promote_compare_fails_when_all_profiles_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "summary.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "FAIL",
                        "risks": ["ci_matrix_failed"],
                        "kpis": {
                            "recommended_profile": "default",
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
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
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            self.assertEqual(len(payload.get("profile_results", [])), 2)
            self.assertEqual(len(payload.get("ranking", [])), 2)

    def test_promote_compare_require_recommended_eligible_fails_when_recommended_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "summary.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": ["strict_profile_downgrade_detected"],
                        "kpis": {
                            "recommended_profile": "industrial_strict",
                            "strict_non_pass_rate": 0.3,
                            "strict_downgrade_rate": 0.2,
                            "review_recovery_rate": 0.9,
                            "fail_rate": 0.1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_compare",
                    "--snapshot",
                    str(snapshot),
                    "--profiles",
                    "default",
                    "industrial_strict",
                    "--require-recommended-eligible",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            self.assertEqual(payload.get("recommended_profile"), "industrial_strict")
            self.assertEqual(payload.get("constraint_reason"), "recommended_profile_failed")

    def test_promote_compare_applies_override_map(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            override = root / "override_allow.json"
            override_map = root / "override_map.json"
            out = root / "summary.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "FAIL",
                        "risks": ["ci_matrix_failed"],
                        "kpis": {"recommended_profile": "industrial_strict"},
                    }
                ),
                encoding="utf-8",
            )
            override.write_text(
                json.dumps(
                    {
                        "allow_promote": True,
                        "reason": "compare override",
                        "approved_by": "human.reviewer",
                        "expires_utc": "2099-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            override_map.write_text(json.dumps({"industrial_strict": str(override)}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_compare",
                    "--snapshot",
                    str(snapshot),
                    "--profiles",
                    "default",
                    "industrial_strict",
                    "--override-map",
                    str(override_map),
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
            self.assertEqual(payload.get("best_profile"), "industrial_strict")
            rows = payload.get("profile_results", [])
            industrial = next((r for r in rows if r.get("profile") == "industrial_strict"), {})
            self.assertEqual(industrial.get("decision"), "PASS")
            self.assertEqual(industrial.get("override_path"), str(override))

    def test_promote_compare_recommended_bonus_influences_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "summary.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": [],
                        "kpis": {
                            "recommended_profile": "industrial_strict",
                            "strict_non_pass_rate": 0.0,
                            "strict_downgrade_rate": 0.0,
                            "review_recovery_rate": 1.0,
                            "fail_rate": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_compare",
                    "--snapshot",
                    str(snapshot),
                    "--profiles",
                    "default",
                    "industrial_strict",
                    "--score-recommended-bonus",
                    "999",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            ranking = payload.get("ranking", [])
            self.assertGreaterEqual(len(ranking), 2)
            self.assertEqual(ranking[0].get("profile"), "industrial_strict")
            self.assertEqual(payload.get("best_profile"), "industrial_strict")


if __name__ == "__main__":
    unittest.main()
