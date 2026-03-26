"""Tests for agent_modelica_gf_hardpack_runner_v1 preflight helpers."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_gf_hardpack_runner_v1 import (
    _run_one_case,
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

    def test_run_batch_forwards_planner_experience_flags(self) -> None:
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
                    planner_experience_injection="on",
                    planner_experience_max_tokens=320,
                )
                payload = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(summary["planner_experience_injection"], "on")
        self.assertEqual(int(summary["planner_experience_max_tokens"] or 0), 320)
        self.assertEqual(payload["planner_experience_injection"], "on")
        self.assertEqual(int(payload["planner_experience_max_tokens"] or 0), 320)
        _, kwargs = run_one_case.call_args
        self.assertEqual(kwargs["planner_experience_injection"], "on")
        self.assertEqual(int(kwargs["planner_experience_max_tokens"] or 0), 320)

    def test_run_batch_preserves_replay_diagnostics(self) -> None:
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
                    "experience_replay": {
                        "enabled": True,
                        "used": True,
                        "signal_coverage_status": "sufficient_signal_coverage",
                    },
                },
            ):
                summary = run_batch(
                    str(pack),
                    out_path=str(out),
                    experience_replay="on",
                    experience_source="artifacts/replay.json",
                )
                payload = json.loads(out.read_text(encoding="utf-8"))

        self.assertTrue(summary["results"][0]["experience_replay"]["used"])
        self.assertEqual(
            payload["results"][0]["experience_replay"]["signal_coverage_status"],
            "sufficient_signal_coverage",
        )


class TestRunOneCase(unittest.TestCase):
    def test_includes_experience_replay_summary_from_executor_payload(self) -> None:
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
            case = {"mutation_id": "ok", "mutated_model_path": "artifacts/ok.mo"}

            def _fake_subprocess_run(cmd, **kwargs):
                out_path = Path(cmd[cmd.index("--out") + 1])
                out_path.write_text(
                    json.dumps(
                        {
                            "executor_status": "PASS",
                            "check_model_pass": True,
                            "simulate_pass": True,
                            "attempts": [{}, {}],
                            "experience_replay": {
                                "enabled": True,
                                "used": True,
                                "signal_coverage_status": "sufficient_signal_coverage",
                                "priority_reason": "rules_reordered_by_experience",
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch(
                "gateforge.agent_modelica_gf_hardpack_runner_v1.subprocess.run",
                side_effect=_fake_subprocess_run,
            ):
                result = _run_one_case(
                    case,
                    str(pack),
                    "openmodelica/openmodelica:v1.26.1-minimal",
                    "gemini",
                    8,
                    300,
                    experience_replay="on",
                    experience_source="artifacts/replay.json",
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["rounds_used"], 2)
        self.assertEqual(
            result["experience_replay"]["signal_coverage_status"],
            "sufficient_signal_coverage",
        )
        self.assertEqual(
            result["experience_replay"]["priority_reason"],
            "rules_reordered_by_experience",
        )

    def test_includes_planner_experience_injection_summary_from_executor_payload(self) -> None:
        case = {
            "mutation_id": "m1",
            "target_scale": "small",
            "expected_failure_type": "model_check_error",
            "expected_stage": "check",
            "source_model_path": "src.mo",
            "mutated_model_path": "mut.mo",
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".git").mkdir()
            src = root / "src.mo"
            mut = root / "mut.mo"
            src.write_text("model X\nend X;\n", encoding="utf-8")
            mut.write_text("model X\nend X;\n", encoding="utf-8")
            case["source_model_path"] = str(src.relative_to(root))
            case["mutated_model_path"] = str(mut.relative_to(root))
            out = root / "executor.json"
            out.write_text(
                json.dumps(
                    {
                        "executor_status": "PASS",
                        "attempts": [],
                        "planner_experience_injection": {
                            "enabled": True,
                            "used": True,
                            "hint_count": 2,
                            "caution_count": 1,
                            "prompt_token_estimate": 180,
                        },
                    }
                ),
                encoding="utf-8",
            )

            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            )
            with mock.patch(
                "gateforge.agent_modelica_gf_hardpack_runner_v1.subprocess.run",
                return_value=completed,
            ):
                with mock.patch(
                    "gateforge.agent_modelica_gf_hardpack_runner_v1.tempfile.NamedTemporaryFile"
                ) as tmp_mock:
                    tmp_ctx = mock.MagicMock()
                    tmp_ctx.__enter__.return_value.name = str(out)
                    tmp_mock.return_value = tmp_ctx
                    result = _run_one_case(
                        case=case,
                        pack_path=str(root / "pack.json"),
                        docker_image="img",
                        planner_backend="gemini",
                        max_rounds=1,
                        timeout_sec=1,
                    )
            self.assertTrue(result["planner_experience_injection"]["used"])
            self.assertEqual(
                result["planner_experience_injection"]["prompt_token_estimate"],
                180,
            )


if __name__ == "__main__":
    unittest.main()
