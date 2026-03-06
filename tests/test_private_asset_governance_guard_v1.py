import json
import subprocess
import unittest
from pathlib import Path


class PrivateAssetGovernanceGuardV1Tests(unittest.TestCase):
    def test_private_asset_paths_are_not_git_tracked(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        tracked = [x.strip() for x in str(proc.stdout or "").splitlines() if x.strip()]
        blocked_prefixes = (
            "benchmarks/private/",
            "policies/private/",
            "data/private_failure_corpus/",
            "data/private_modelica/",
            "data/private_mutations/",
            "data/private_ledger/",
        )
        leaked = [p for p in tracked if p.startswith(blocked_prefixes)]
        self.assertFalse(
            leaked,
            msg="private moat assets must never be git-tracked: " + ", ".join(leaked[:10]),
        )

    def test_public_templates_exist_and_are_marked(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        template_paths = [
            repo_root / "benchmarks" / "agent_modelica_mvp_repair_v1.public_template.json",
            repo_root / "benchmarks" / "agent_modelica_hardpack_v1.public_template.json",
            repo_root / "policies" / "physics_contract_v0.public_template.json",
            repo_root / "policies" / "default_policy.public_template.json",
        ]
        for path in template_paths:
            self.assertTrue(path.exists(), msg=f"missing public template: {path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(
                bool(payload.get("is_public_template")),
                msg=f"template marker missing: {path}",
            )


if __name__ == "__main__":
    unittest.main()
