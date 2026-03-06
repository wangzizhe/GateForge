import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaPrivateAssetGuardV1Tests(unittest.TestCase):
    def _init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init"], cwd=str(root), capture_output=True, text=True, check=False)
        (root / "README.md").write_text("# temp\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=str(root), capture_output=True, text=True, check=False)

    def test_private_asset_guard_passes_when_private_assets_are_untracked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._init_repo(root)
            private_file = root / "benchmarks" / "private" / "local.json"
            private_file.parent.mkdir(parents=True, exist_ok=True)
            private_file.write_text("{}", encoding="utf-8")
            out = root / "out.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_private_asset_guard_v1",
                    "--repo-root",
                    str(root),
                    "--private-path",
                    "benchmarks/private",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(str(payload.get("status") or ""), "PASS")
            self.assertEqual(int(payload.get("tracked_private_file_count") or 0), 0)

    def test_private_asset_guard_fails_when_private_assets_are_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._init_repo(root)
            private_file = root / "policies" / "private" / "physics_contract_v0.json"
            private_file.parent.mkdir(parents=True, exist_ok=True)
            private_file.write_text("{}", encoding="utf-8")
            subprocess.run(
                ["git", "add", str(private_file.relative_to(root))],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
            )
            out = root / "out.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_private_asset_guard_v1",
                    "--repo-root",
                    str(root),
                    "--private-path",
                    "policies/private",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(str(payload.get("status") or ""), "FAIL")
            self.assertEqual(int(payload.get("tracked_private_file_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()
