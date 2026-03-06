import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaRunSnapshotV1Tests(unittest.TestCase):
    def test_snapshot_pass_when_files_exist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_snapshot_") as td:
            root = Path(td)
            profile = root / "profile.json"
            profile.write_text("{}", encoding="utf-8")
            out = root / "snapshot.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_snapshot_v1",
                    "--run-id",
                    "r1",
                    "--repo-root",
                    ".",
                    "--profile-path",
                    str(profile),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("run_id"), "r1")

    def test_snapshot_needs_review_when_missing_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_snapshot_") as td:
            root = Path(td)
            out = root / "snapshot.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_snapshot_v1",
                    "--run-id",
                    "r2",
                    "--profile-path",
                    str(root / "missing.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertTrue(bool(payload.get("missing_files")))


if __name__ == "__main__":
    unittest.main()
