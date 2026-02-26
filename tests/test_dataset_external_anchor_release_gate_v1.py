import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetExternalAnchorReleaseGateV1Tests(unittest.TestCase):
    def test_gate_pass_with_allow_decision(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            scoreboard = root / "scoreboard.json"
            pack = root / "pack.json"
            provenance = root / "provenance.json"
            contract = root / "contract.json"
            out = root / "summary.json"

            anchor.write_text(json.dumps({"status": "PASS", "public_release_score": 88.0}), encoding="utf-8")
            scoreboard.write_text(json.dumps({"status": "PASS", "moat_public_score": 86.0}), encoding="utf-8")
            pack.write_text(json.dumps({"status": "PASS", "pack_readiness_score": 85.0}), encoding="utf-8")
            provenance.write_text(
                json.dumps({"status": "PASS", "provenance_completeness_pct": 98.0, "unknown_license_ratio_pct": 0.0}),
                encoding="utf-8",
            )
            contract.write_text(json.dumps({"status": "PASS", "fail_count": 0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_external_anchor_release_gate_v1",
                    "--anchor-public-release-summary",
                    str(anchor),
                    "--moat-public-scoreboard-summary",
                    str(scoreboard),
                    "--large-model-benchmark-pack-summary",
                    str(pack),
                    "--modelica-library-provenance-guard-summary",
                    str(provenance),
                    "--optional-ci-contract-summary",
                    str(contract),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("gate_decision"), "ALLOW")

    def test_gate_needs_review_when_warnings_exist(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            scoreboard = root / "scoreboard.json"
            pack = root / "pack.json"
            provenance = root / "provenance.json"
            contract = root / "contract.json"
            out = root / "summary.json"

            anchor.write_text(json.dumps({"status": "NEEDS_REVIEW", "public_release_score": 74.0}), encoding="utf-8")
            scoreboard.write_text(json.dumps({"status": "PASS", "moat_public_score": 76.0}), encoding="utf-8")
            pack.write_text(json.dumps({"status": "PASS", "pack_readiness_score": 78.0}), encoding="utf-8")
            provenance.write_text(
                json.dumps({"status": "PASS", "provenance_completeness_pct": 96.0, "unknown_license_ratio_pct": 2.0}),
                encoding="utf-8",
            )
            contract.write_text(json.dumps({"status": "PASS", "fail_count": 0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_external_anchor_release_gate_v1",
                    "--anchor-public-release-summary",
                    str(anchor),
                    "--moat-public-scoreboard-summary",
                    str(scoreboard),
                    "--large-model-benchmark-pack-summary",
                    str(pack),
                    "--modelica-library-provenance-guard-summary",
                    str(provenance),
                    "--optional-ci-contract-summary",
                    str(contract),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertEqual(summary.get("gate_decision"), "NEEDS_REVIEW")

    def test_gate_fails_when_blocker_exists(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            scoreboard = root / "scoreboard.json"
            pack = root / "pack.json"
            provenance = root / "provenance.json"
            contract = root / "contract.json"
            out = root / "summary.json"

            anchor.write_text(json.dumps({"status": "PASS", "public_release_score": 88.0}), encoding="utf-8")
            scoreboard.write_text(json.dumps({"status": "PASS", "moat_public_score": 83.0}), encoding="utf-8")
            pack.write_text(json.dumps({"status": "PASS", "pack_readiness_score": 82.0}), encoding="utf-8")
            provenance.write_text(
                json.dumps({"status": "PASS", "provenance_completeness_pct": 98.0, "unknown_license_ratio_pct": 0.0}),
                encoding="utf-8",
            )
            contract.write_text(json.dumps({"status": "FAIL", "fail_count": 3}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_external_anchor_release_gate_v1",
                    "--anchor-public-release-summary",
                    str(anchor),
                    "--moat-public-scoreboard-summary",
                    str(scoreboard),
                    "--large-model-benchmark-pack-summary",
                    str(pack),
                    "--modelica-library-provenance-guard-summary",
                    str(provenance),
                    "--optional-ci-contract-summary",
                    str(contract),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertEqual(summary.get("gate_decision"), "BLOCK")


if __name__ == "__main__":
    unittest.main()
