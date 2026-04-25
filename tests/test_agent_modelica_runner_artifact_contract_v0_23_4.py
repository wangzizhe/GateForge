from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_runner_artifact_contract_v0_23_4 import (
    build_artifact_manifest,
    build_runner_artifact_contract,
    validate_artifact_manifest,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class RunnerArtifactContractV0234Tests(unittest.TestCase):
    def test_build_artifact_manifest_uses_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifacts" / "demo"
            _write_json(artifact_dir / "summary.json", {"version": "v0.test", "status": "PASS"})

            manifest = build_artifact_manifest(
                {
                    "run_version": "v0.test",
                    "artifact_dir": artifact_dir,
                    "producer_script": "scripts/demo.py",
                    "expected_files": ["summary.json"],
                },
                repo_root=root,
            )

            self.assertEqual(manifest["artifact_dir"], "artifacts/demo")
            self.assertEqual(validate_artifact_manifest(manifest), [])

    def test_validate_artifact_manifest_flags_missing_files(self) -> None:
        manifest = {
            "contract_version": "runner_artifact_contract_v1",
            "run_version": "v0.test",
            "artifact_dir": "artifacts/demo",
            "producer_script": "scripts/demo.py",
            "expected_files": ["summary.json"],
            "present_files": [],
            "missing_files": ["summary.json"],
            "summary_status": "UNKNOWN",
            "environment_metadata": {},
            "provider_metadata": {},
            "budget_metadata": {},
        }

        self.assertIn("missing_expected_files", validate_artifact_manifest(manifest))

    def test_build_runner_artifact_contract_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifacts" / "demo"
            _write_json(artifact_dir / "summary.json", {"version": "v0.test", "status": "PASS"})
            out_dir = root / "out"

            summary = build_runner_artifact_contract(
                run_specs=[
                    {
                        "run_version": "v0.test",
                        "artifact_dir": artifact_dir,
                        "producer_script": "scripts/demo.py",
                        "expected_files": ["summary.json"],
                    }
                ],
                out_dir=out_dir,
                repo_root=root,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["manifest_count"], 1)
            self.assertTrue((out_dir / "artifact_manifests.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
