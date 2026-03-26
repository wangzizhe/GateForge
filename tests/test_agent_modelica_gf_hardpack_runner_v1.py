"""Tests for agent_modelica_gf_hardpack_runner_v1 preflight helpers."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_gf_hardpack_runner_v1 import (
    infer_project_root_from_pack,
    run_batch,
    validate_hardpack_cases,
)


def _write_pack(pack_path: Path, cases: list[dict]) -> None:
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        json.dumps({"schema_version": "hardpack_v1", "cases": cases}),
        encoding="utf-8",
    )


class TestInferProjectRootFromPack(unittest.TestCase):
    def test_prefers_nearest_git_ancestor_for_private_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            pack = root / "benchmarks" / "private" / "pack.json"
            _write_pack(pack, [])
            self.assertEqual(infer_project_root_from_pack(str(pack)).resolve(), root.resolve())


class TestValidateHardpackCases(unittest.TestCase):
    def test_reports_missing_mutated_model_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            existing = root / "artifacts" / "ok.mo"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("model Ok end Ok;", encoding="utf-8")
            pack = root / "benchmarks" / "private" / "pack.json"
            cases = [
                {"mutation_id": "ok", "mutated_model_path": "artifacts/ok.mo"},
                {"mutation_id": "missing", "mutated_model_path": "artifacts/missing.mo"},
            ]
            _write_pack(pack, cases)

            validation = validate_hardpack_cases(str(pack), cases)

        self.assertFalse(validation["is_complete"])
        self.assertEqual(validation["missing_mutated_model_count"], 1)
        self.assertEqual(validation["missing_cases"][0]["mutation_id"], "missing")
        self.assertTrue(validation["missing_cases"][0]["resolved_mutated_model_path"].endswith("artifacts/missing.mo"))


class TestRunBatchPreflight(unittest.TestCase):
    def test_run_batch_fails_fast_on_incomplete_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            pack = root / "benchmarks" / "private" / "pack.json"
            _write_pack(
                pack,
                [{"mutation_id": "missing", "mutated_model_path": "artifacts/missing.mo"}],
            )
            out = root / "out.json"

            with mock.patch(
                "gateforge.agent_modelica_gf_hardpack_runner_v1._run_one_case"
            ) as run_one_case:
                summary = run_batch(str(pack), out_path=str(out))
                payload = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["error"], "hardpack_incomplete")
        self.assertEqual(summary["pack_validation"]["missing_mutated_model_count"], 1)
        run_one_case.assert_not_called()
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["error"], "hardpack_incomplete")

    def test_run_batch_forwards_experience_replay_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            mutated = root / "artifacts" / "ok.mo"
            mutated.parent.mkdir(parents=True, exist_ok=True)
            mutated.write_text("model Ok end Ok;", encoding="utf-8")
            pack = root / "benchmarks" / "private" / "pack.json"
            _write_pack(
                pack,
                [{"mutation_id": "ok", "mutated_model_path": "artifacts/ok.mo"}],
            )
            out = root / "out.json"

            with mock.patch(
                "gateforge.agent_modelica_gf_hardpack_runner_v1._run_one_case",
                return_value={
                    "mutation_id": "ok",
                    "target_scale": "",
                    "expected_failure_type": "",
                    "success": True,
                    "executor_status": "PASS",
                    "elapsed_sec": 1.0,
                    "error": None,
                },
            ) as run_one_case:
                summary = run_batch(
                    str(pack),
                    out_path=str(out),
                    experience_replay="on",
                    experience_source="artifacts/replay.json",
                )
                payload = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(summary["experience_replay"], "on")
        self.assertEqual(summary["experience_source"], "artifacts/replay.json")
        self.assertEqual(payload["experience_replay"], "on")
        self.assertEqual(payload["experience_source"], "artifacts/replay.json")
        _, kwargs = run_one_case.call_args
        self.assertEqual(kwargs["experience_replay"], "on")
        self.assertEqual(kwargs["experience_source"], "artifacts/replay.json")


if __name__ == "__main__":
    unittest.main()
