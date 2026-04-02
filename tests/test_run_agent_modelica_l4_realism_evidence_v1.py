import json
import os
import subprocess
import tempfile
import time
import unittest
import hashlib
from pathlib import Path
from unittest import mock

import gateforge.agent_modelica_realism_run_lifecycle_v1 as realism_lifecycle
from gateforge.agent_modelica_realism_run_lifecycle_v1 import _runtime_config


def _cmd_pass() -> str:
    return "python3 -m gateforge.agent_modelica_live_executor_mock_v0"


def _cmd_l4_switch() -> str:
    return 'python3 -m gateforge.agent_modelica_live_executor_mock_l4_switch_v0 --l4-enabled "__L4_ENABLED__"'


def _build_taskset(path: Path) -> None:
    payload = {
        "schema_version": "agent_modelica_taskset_v1",
        "tasks": [
            {"task_id": "t_under_small", "scale": "small", "failure_type": "underconstrained_system", "category": "topology_wiring", "expected_stage": "check"},
            {"task_id": "t_under_medium", "scale": "medium", "failure_type": "underconstrained_system", "category": "topology_wiring", "expected_stage": "check"},
            {"task_id": "t_conn_small", "scale": "small", "failure_type": "connector_mismatch", "category": "topology_wiring", "expected_stage": "check"},
            {"task_id": "t_conn_medium", "scale": "medium", "failure_type": "connector_mismatch", "category": "topology_wiring", "expected_stage": "check"},
            {"task_id": "t_init_small", "scale": "small", "failure_type": "initialization_infeasible", "category": "initialization", "expected_stage": "simulate"},
            {"task_id": "t_init_medium", "scale": "medium", "failure_type": "initialization_infeasible", "category": "initialization", "expected_stage": "simulate"},
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_realism_manifest(taskset_path: Path, *, builder_sha: str) -> None:
    _write_json(
        taskset_path.parent / "manifest.json",
        {
            "schema_version": "agent_modelica_electrical_realism_frozen_taskset_v1",
            "builder_provenance": {
                "builder_source_path": "gateforge/agent_modelica_electrical_mutant_taskset_v0.py",
                "builder_source_sha": builder_sha,
            },
        },
    )


def _build_legacy_artifacts(out_dir: Path) -> None:
    _write_json(
        out_dir / "environment_preflight_summary.json",
        {
            "schema_version": "agent_modelica_realism_environment_preflight_v1",
            "status": "BLOCKED",
            "backend": "openmodelica_docker",
            "challenge_planner_backend": "gemini",
            "blockers": ["missing_gemini_api_key"],
        },
    )
    _write_json(
        out_dir / "summary.json",
        {
            "schema_version": "agent_modelica_l4_uplift_evidence_bundle_v0",
            "status": "BLOCKED",
            "decision": "blocked",
            "primary_reason": "environment_preflight_failed",
            "pack_id": "agent_modelica_realism_pack_v1",
            "pack_version": "v1",
            "pack_track": "realism",
            "acceptance_scope": "independent_validation",
        },
    )
    _write_json(
        out_dir / "challenge" / "frozen_summary.json",
        {
            "schema_version": "agent_modelica_l4_challenge_frozen_summary_v0",
            "status": "PASS",
            "pack_id": "agent_modelica_realism_pack_v1",
            "pack_version": "v1",
            "pack_track": "realism",
            "acceptance_scope": "independent_validation",
            "baseline_off_success_at_k_pct": 100.0,
            "baseline_has_headroom": False,
            "counts_by_failure_type": {
                "underconstrained_system": 2,
                "connector_mismatch": 2,
                "initialization_infeasible": 2,
            },
            "counts_by_category": {
                "topology_wiring": 4,
                "initialization": 2,
            },
        },
    )
    _write_json(
        out_dir / "challenge" / "manifest.json",
        {
            "baseline_provenance": {
                "planner_backend": "gemini",
                "llm_model": "gemini-3.1-pro-preview",
                "backend": "openmodelica_docker",
            }
        },
    )
    _build_taskset(out_dir / "challenge" / "taskset_frozen.json")
    _write_json(
        out_dir / "main_sweep" / "summary.json",
        {
            "status": "PASS",
            "recommended_profile": "score_v1",
            "profiles": {
                "score_v1": {
                    "success_at_k_pct_on": 66.67,
                    "success_at_k_pct_off": 33.33,
                }
            },
        },
    )
    _write_json(out_dir / "night_sweep" / "summary.json", {})
    _write_json(out_dir / "main_l5" / "l5_eval_summary.json", {})
    _write_json(out_dir / "night_l5" / "l5_eval_summary.json", {})


class RunAgentModelicaL4RealismEvidenceV1Tests(unittest.TestCase):
    def _run_script(self, *, env: dict[str, str], repo_root: Path) -> subprocess.CompletedProcess[str]:
        script = repo_root / "scripts" / "run_agent_modelica_l4_realism_evidence_v1.sh"
        return subprocess.run(
            ["bash", str(script)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=900,
        )

    def _run_resume_script(self, *, env: dict[str, str], repo_root: Path) -> subprocess.CompletedProcess[str]:
        script = repo_root / "scripts" / "resume_agent_modelica_l4_realism_run_v1.sh"
        return subprocess.run(
            ["bash", str(script)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=900,
        )

    def test_active_run_lock_blocks_second_invocation_for_same_out_dir(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            run_root = out_dir / "runs" / "active01"
            out_dir.mkdir(parents=True, exist_ok=True)
            _build_taskset(taskset)
            (out_dir / ".active_run_lock.json").write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_realism_run_lock_v1",
                        "pid": os.getpid(),
                        "run_id": "active01",
                        "run_root": str(run_root),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "active02",
            }
            proc = self._run_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 3, msg=proc.stderr or proc.stdout)
            self.assertIn("active_run_lock", proc.stdout)
            self.assertFalse((out_dir / "runs" / "active02").exists())

    def test_stale_run_lock_does_not_block_followup_invocation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            run_root = out_dir / "runs" / "stale01"
            out_dir.mkdir(parents=True, exist_ok=True)
            _build_taskset(taskset)
            (out_dir / ".active_run_lock.json").write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_realism_run_lock_v1",
                        "pid": 999999,
                        "run_id": "stale-lock",
                        "run_root": str(out_dir / "runs" / "stale-lock"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "stale01",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LLM_MODEL": " ",
                "LLM_MODEL": "",
                "GATEFORGE_GEMINI_MODEL": "",
                "GOOGLE_API_KEY": "",
                "GEMINI_API_KEY": "",
            }
            proc = self._run_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 2, msg=proc.stderr or proc.stdout)
            self.assertTrue(run_root.exists())
            self.assertTrue((run_root / "run_manifest.json").exists())
            preflight = json.loads((run_root / "environment_preflight_summary.json").read_text(encoding="utf-8"))
            self.assertIn("missing_llm_model", preflight.get("blockers") or [])

    def test_blocked_run_is_run_scoped_and_does_not_update_latest(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            run_root = out_dir / "runs" / "blocked01"
            _build_taskset(taskset)
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "blocked01",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LLM_MODEL": " ",
                "LLM_MODEL": "",
                "GATEFORGE_GEMINI_MODEL": "",
                "GOOGLE_API_KEY": "",
                "GEMINI_API_KEY": "",
            }
            proc = self._run_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 2, msg=proc.stderr or proc.stdout)
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            run_status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
            preflight = json.loads((run_root / "environment_preflight_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final_summary.get("status"), "BLOCKED")
            self.assertEqual(final_summary.get("primary_reason"), "environment_preflight_failed")
            self.assertTrue(bool(run_status.get("finalized")))
            self.assertIn("missing_llm_model", preflight.get("blockers") or [])
            self.assertFalse((out_dir / "latest_summary.json").exists())
            self.assertFalse((out_dir / "latest_run.json").exists())

    def test_resume_main_l5_refreshes_live_budget_and_clears_budget_stop_when_limit_increased(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_root = root / "runs" / "r1"
            run_root.mkdir(parents=True, exist_ok=True)
            realism_lifecycle.init_run(
                out_dir=str(root),
                run_root=str(run_root),
                run_id="r1",
                pack_id="p",
                pack_version="v1",
                pack_track="realism",
                acceptance_scope="independent_validation",
                base_taskset="taskset.json",
                lock_path="",
                update_latest=False,
                runtime_config={"night_enabled": 0},
            )
            _write_json(
                run_root / "private" / "live_request_ledger.json",
                {
                    "schema_version": "agent_modelica_live_request_ledger_v1",
                    "live_budget": {
                        "max_requests_per_run": 80,
                        "max_consecutive_429": 3,
                        "base_backoff_sec": 5.0,
                        "max_backoff_sec": 60.0,
                    },
                    "request_count": 81,
                    "rate_limit_429_count": 0,
                    "consecutive_429_count": 0,
                    "backoff_count": 0,
                    "last_backoff_sec": 0.0,
                    "budget_stop_triggered": True,
                    "last_stop_reason": "live_request_budget_exceeded",
                    "last_stage": "main_l5",
                },
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN": "140",
                    "GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429": "4",
                    "GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC": "2",
                    "GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC": "30",
                },
                clear=False,
            ):
                realism_lifecycle._reset_live_ledger_for_resume(run_root, "main_l5")
            ledger = json.loads((run_root / "private" / "live_request_ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["live_budget"]["max_requests_per_run"], 140)
            self.assertEqual(ledger["live_budget"]["max_consecutive_429"], 4)
            self.assertEqual(ledger["live_budget"]["base_backoff_sec"], 2.0)
            self.assertEqual(ledger["live_budget"]["max_backoff_sec"], 30.0)
            self.assertFalse(ledger["budget_stop_triggered"])
            self.assertEqual(ledger["last_stop_reason"], "")
            self.assertEqual(ledger["last_stage"], "main_l5")

    def test_resume_main_l5_force_rerun_resets_live_budget_window(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_root = root / "runs" / "r1"
            run_root.mkdir(parents=True, exist_ok=True)
            _write_json(
                run_root / "private" / "live_request_ledger.json",
                {
                    "schema_version": "agent_modelica_live_request_ledger_v1",
                    "live_budget": {
                        "max_requests_per_run": 80,
                        "max_consecutive_429": 3,
                        "base_backoff_sec": 5.0,
                        "max_backoff_sec": 60.0,
                    },
                    "request_count": 101,
                    "rate_limit_429_count": 12,
                    "consecutive_429_count": 3,
                    "backoff_count": 4,
                    "last_backoff_sec": 10.0,
                    "budget_stop_triggered": True,
                    "last_stop_reason": "live_request_budget_exceeded",
                    "last_stage": "main_l5",
                },
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN": "140",
                },
                clear=False,
            ):
                realism_lifecycle._reset_live_ledger_for_resume(
                    run_root,
                    "main_l5",
                    restart_budget_window=True,
                )
            ledger = json.loads((run_root / "private" / "live_request_ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["request_count"], 0)
            self.assertEqual(ledger["rate_limit_429_count"], 0)
            self.assertEqual(ledger["backoff_count"], 0)
            self.assertFalse(ledger["budget_stop_triggered"])
            self.assertEqual(ledger["last_stop_reason"], "")

    def test_resume_main_l5_disable_live_budget_sets_unbounded_budget(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_root = root / "runs" / "r1"
            run_root.mkdir(parents=True, exist_ok=True)
            _write_json(
                run_root / "private" / "live_request_ledger.json",
                {
                    "schema_version": "agent_modelica_live_request_ledger_v1",
                    "live_budget": {
                        "max_requests_per_run": 80,
                        "max_consecutive_429": 3,
                        "base_backoff_sec": 5.0,
                        "max_backoff_sec": 60.0,
                    },
                    "request_count": 80,
                    "rate_limit_429_count": 0,
                    "consecutive_429_count": 0,
                    "backoff_count": 0,
                    "last_backoff_sec": 0.0,
                    "budget_stop_triggered": True,
                    "last_stop_reason": "live_request_budget_exceeded",
                    "last_stage": "main_l5",
                },
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GATEFORGE_AGENT_L4_REALISM_DISABLE_LIVE_BUDGET": "1",
                },
                clear=False,
            ):
                realism_lifecycle._reset_live_ledger_for_resume(run_root, "main_l5")
            ledger = json.loads((run_root / "private" / "live_request_ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["live_budget"]["max_requests_per_run"], 0)
            self.assertFalse(ledger["budget_stop_triggered"])
            self.assertEqual(ledger["last_stop_reason"], "")
            self.assertEqual(ledger["last_stage"], "main_l5")

    def test_stale_base_taskset_blocks_preflight(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        builder_path = repo_root / "gateforge" / "agent_modelica_electrical_mutant_taskset_v0.py"
        current_sha = hashlib.sha256(builder_path.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset_frozen.json"
            out_dir = root / "out"
            run_root = out_dir / "runs" / "stalepack01"
            _build_taskset(taskset)
            _write_realism_manifest(taskset, builder_sha=("0" * len(current_sha)))
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "stalepack01",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LLM_MODEL": "mock-model",
                "GOOGLE_API_KEY": "dummy",
            }
            proc = self._run_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 2, msg=proc.stderr or proc.stdout)
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            preflight = json.loads((run_root / "environment_preflight_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final_summary.get("status"), "BLOCKED")
            self.assertEqual(final_summary.get("primary_reason"), "stale_base_taskset")
            self.assertIn("stale_base_taskset", preflight.get("blockers") or [])

    def test_full_chain_outputs_run_scoped_bundle_and_updates_latest(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        report_script = repo_root / "scripts" / "report_agent_modelica_l4_realism_run_status_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            run_root = out_dir / "runs" / "success01"
            _build_taskset(taskset)
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "success01",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MIN_OFF_SUCCESS_PCT": "0",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MAX_OFF_SUCCESS_PCT": "100",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = self._run_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            run_status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
            evidence_summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            latest_run = json.loads((out_dir / "latest_run.json").read_text(encoding="utf-8"))
            latest_summary = json.loads((out_dir / "latest_summary.json").read_text(encoding="utf-8"))
            latest_realism = json.loads((out_dir / "latest_realism_internal_summary.json").read_text(encoding="utf-8"))
            challenge = json.loads((run_root / "challenge" / "frozen_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(final_summary.get("run_id"), "success01")
            self.assertEqual(final_summary.get("baseline_state"), "baseline_saturated")
            self.assertEqual(str(final_summary.get("realism_mode") or ""), "lean")
            self.assertFalse(bool(final_summary.get("night_enabled")))
            self.assertEqual(evidence_summary.get("status"), "PASS")
            self.assertFalse(bool(evidence_summary.get("night_enabled")))
            self.assertNotIn("missing_night_sweep_summary", set(evidence_summary.get("reasons") or []))
            self.assertNotIn("missing_night_l5_eval_summary", set(evidence_summary.get("reasons") or []))
            self.assertTrue(bool(run_status.get("finalized")))
            self.assertTrue(bool(run_status.get("latest_updated")))
            self.assertEqual(latest_run.get("run_id"), "success01")
            self.assertEqual(latest_summary.get("run_id"), "success01")
            self.assertIn(latest_realism.get("status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertEqual(int((challenge.get("counts_by_category") or {}).get("topology_wiring") or 0), 4)
            self.assertEqual(int((challenge.get("counts_by_category") or {}).get("initialization") or 0), 2)
            for stage in ("preflight", "challenge", "main_sweep", "night_sweep", "main_l5", "night_l5", "realism_summary", "finalize"):
                self.assertTrue((run_root / "stages" / stage / "stage_status.json").exists(), msg=stage)

            report = subprocess.run(
                ["bash", str(report_script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**env, "GATEFORGE_AGENT_L4_REALISM_RUN_ID": ""},
                timeout=120,
            )
            self.assertEqual(report.returncode, 0, msg=report.stderr or report.stdout)
            report_payload = json.loads(report.stdout.strip().splitlines()[-1])
            self.assertEqual(report_payload.get("run_id"), "success01")
            self.assertTrue(bool(report_payload.get("finalized")))
            self.assertEqual(report_payload.get("run_mode"), "scoped")
            self.assertIn("challenge", report_payload.get("completed_stages") or [])
            self.assertEqual(report_payload.get("active_pid"), None)

    def test_finalize_surfaces_rate_limit_budget_stop_reason(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            run_root = out_dir / "runs" / "ratelimit01"
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / "challenge").mkdir(parents=True, exist_ok=True)
            _build_taskset(run_root / "challenge" / "taskset_frozen.json")
            _write_json(
                run_root / "run_manifest.json",
                {
                    "schema_version": "agent_modelica_realism_run_manifest_v1",
                    "run_id": "ratelimit01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                },
            )
            _write_json(
                run_root / "run_status.json",
                {
                    "schema_version": "agent_modelica_realism_run_status_v1",
                    "run_id": "ratelimit01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "status": "RUNNING",
                    "current_stage": "main_sweep",
                    "finalized": False,
                    "latest_updated": False,
                    "stages": {},
                },
            )
            _write_json(
                run_root / "summary.json",
                {
                    "schema_version": "agent_modelica_l4_uplift_evidence_bundle_v0",
                    "status": "PASS",
                    "decision": "hold",
                    "primary_reason": "rate_limited",
                    "live_budget_stop_reason": "rate_limited",
                    "budget_stop_triggered": True,
                    "realism_mode": "lean",
                    "night_enabled": False,
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                },
            )
            _write_json(
                run_root / "challenge" / "frozen_summary.json",
                {
                    "schema_version": "agent_modelica_l4_challenge_pack_v0",
                    "status": "PASS",
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "baseline_off_success_at_k_pct": 0.0,
                    "baseline_off_record_count": 6,
                    "baseline_execution_valid": True,
                    "baseline_meets_minimum": False,
                    "baseline_has_headroom": True,
                    "counts_by_failure_type": {
                        "underconstrained_system": 2,
                        "connector_mismatch": 2,
                        "initialization_infeasible": 2,
                    },
                    "counts_by_category": {
                        "topology_wiring": 4,
                        "initialization": 2,
                    },
                },
            )
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "finalize-run",
                    "--out-dir",
                    str(out_dir),
                    "--run-root",
                    str(run_root),
                    "--update-latest",
                    "0",
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final_summary.get("status"), "BLOCKED")
            self.assertEqual(final_summary.get("primary_reason"), "rate_limited")
            self.assertTrue(bool(final_summary.get("budget_stop_triggered")))

    def test_realism_wrapper_continues_after_weak_baseline_by_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            run_root = out_dir / "runs" / "weakreal01"
            _build_taskset(taskset)
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "weakreal01",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = self._run_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            evidence_summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            main_l5 = json.loads((run_root / "main_l5" / "l5_eval_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final_summary.get("primary_reason"), "baseline_too_weak")
            self.assertTrue(bool(final_summary.get("continued_after_weak_baseline")))
            self.assertTrue(bool(evidence_summary.get("continued_after_weak_baseline")))
            self.assertNotEqual(final_summary.get("taxonomy_alignment_status"), "INCOMPLETE")
            self.assertTrue(bool(main_l5))

    def test_blocked_run_does_not_replace_existing_latest_pointers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            _build_taskset(taskset)
            success_env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "success02",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MIN_OFF_SUCCESS_PCT": "0",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MAX_OFF_SUCCESS_PCT": "100",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            success_proc = self._run_script(env=success_env, repo_root=repo_root)
            self.assertEqual(success_proc.returncode, 0, msg=success_proc.stderr or success_proc.stdout)

            blocked_env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "blocked02",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LLM_MODEL": " ",
                "LLM_MODEL": "",
                "GATEFORGE_GEMINI_MODEL": "",
                "GOOGLE_API_KEY": "",
                "GEMINI_API_KEY": "",
            }
            blocked_proc = self._run_script(env=blocked_env, repo_root=repo_root)
            self.assertEqual(blocked_proc.returncode, 2, msg=blocked_proc.stderr or blocked_proc.stdout)

            latest_run = json.loads((out_dir / "latest_run.json").read_text(encoding="utf-8"))
            latest_summary = json.loads((out_dir / "latest_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_run.get("run_id"), "success02")
            self.assertEqual(latest_summary.get("run_id"), "success02")

    def test_report_identifies_legacy_active_run_and_missing_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        report_script = repo_root / "scripts" / "report_agent_modelica_l4_realism_run_status_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            _build_legacy_artifacts(out_dir)
            sleeper = subprocess.Popen(
                [
                    "python3",
                    "-c",
                    "import time; time.sleep(30)",
                    "agent_modelica_run_contract_v1",
                    str(out_dir),
                ],
                cwd=str(repo_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                time.sleep(1)
                _write_json(out_dir / ".legacy_active_pid.json", {"pid": sleeper.pid})
                report = subprocess.run(
                    ["bash", str(report_script)],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir)},
                    timeout=120,
                )
                self.assertEqual(report.returncode, 0, msg=report.stderr or report.stdout)
                payload = json.loads(report.stdout.strip().splitlines()[-1])
                self.assertEqual(payload.get("run_mode"), "legacy")
                self.assertEqual(int(payload.get("active_pid") or 0), sleeper.pid)
                self.assertIn("challenge", payload.get("completed_stages") or [])
                self.assertIn("main_sweep", payload.get("completed_stages") or [])
                self.assertIn("night_sweep", payload.get("missing_stages") or [])
                self.assertEqual(payload.get("current_stage"), "night_sweep")
                self.assertFalse(bool(payload.get("finalize_ready")))
            finally:
                sleeper.terminate()
                sleeper.wait(timeout=10)

    def test_watcher_adopts_legacy_run_and_finalizes_needs_review(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        watch_script = repo_root / "scripts" / "watch_agent_modelica_l4_realism_run_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            _build_legacy_artifacts(out_dir)
            proc = subprocess.run(
                ["bash", str(watch_script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_L4_REALISM_WATCH_INTERVAL_SEC": "0",
                    "GATEFORGE_AGENT_L4_REALISM_WATCH_MAX_POLLS": "1",
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(payload.get("run_mode"), "scoped")
            self.assertTrue(bool(payload.get("finalized")))
            run_root = out_dir / "runs" / "legacy_adopted_v1"
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
            latest_summary = json.loads((out_dir / "latest_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final_summary.get("status"), "NEEDS_REVIEW")
            self.assertEqual(final_summary.get("primary_reason"), "downstream_evidence_incomplete")
            self.assertEqual(final_summary.get("baseline_state"), "baseline_saturated")
            self.assertEqual(final_summary.get("taxonomy_alignment_status"), "INCOMPLETE")
            self.assertEqual(manifest.get("run_origin"), "legacy_adoption")
            self.assertEqual(manifest.get("legacy_source_out_dir"), str(out_dir))
            self.assertEqual(latest_summary.get("run_id"), "legacy_adopted_v1")

    def test_report_recommends_resume_for_partial_scoped_run(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        report_script = repo_root / "scripts" / "report_agent_modelica_l4_realism_run_status_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            _build_legacy_artifacts(out_dir)
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "adopt-legacy",
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            report = subprocess.run(
                ["bash", str(report_script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "legacy_adopted_v1",
                },
                timeout=120,
            )
            self.assertEqual(report.returncode, 0, msg=report.stderr or report.stdout)
            payload = json.loads(report.stdout.strip().splitlines()[-1])
            self.assertEqual(payload.get("run_mode"), "scoped")
            self.assertTrue(bool(payload.get("resume_recommended")))
            self.assertEqual(payload.get("next_resume_stages"), ["night_sweep", "main_l5", "night_l5"])
            self.assertEqual(payload.get("resume_blockers"), [])

    def test_finalize_marks_baseline_execution_failure_and_blocks_taxonomy_artifacts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            run_root = out_dir / "runs" / "baseline_exec_fail01"
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / "challenge").mkdir(parents=True, exist_ok=True)
            _build_taskset(run_root / "challenge" / "taskset_frozen.json")
            _write_json(
                run_root / "run_manifest.json",
                {
                    "schema_version": "agent_modelica_realism_run_manifest_v1",
                    "run_id": "baseline_exec_fail01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                },
            )
            _write_json(
                run_root / "run_status.json",
                {
                    "schema_version": "agent_modelica_realism_run_status_v1",
                    "run_id": "baseline_exec_fail01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "status": "RUNNING",
                    "current_stage": "challenge",
                    "finalized": False,
                    "latest_updated": False,
                    "stages": {},
                },
            )
            _write_json(
                run_root / "summary.json",
                {
                    "schema_version": "agent_modelica_l4_uplift_evidence_bundle_v0",
                    "status": "PASS",
                    "decision": "hold",
                    "primary_reason": "baseline_execution_failed",
                    "acceptance_mode": "delta_uplift",
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                },
            )
            _write_json(
                run_root / "challenge" / "frozen_summary.json",
                {
                    "schema_version": "agent_modelica_l4_challenge_pack_v0",
                    "status": "FAIL",
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "baseline_off_success_at_k_pct": None,
                    "baseline_off_record_count": 0,
                    "baseline_execution_valid": False,
                    "baseline_meets_minimum": None,
                    "baseline_has_headroom": None,
                    "counts_by_failure_type": {
                        "underconstrained_system": 2,
                        "connector_mismatch": 2,
                        "initialization_infeasible": 2,
                    },
                    "counts_by_category": {
                        "topology_wiring": 4,
                        "initialization": 2,
                    },
                    "reasons": ["baseline_off_run_results_empty", "baseline_execution_failed"],
                },
            )
            _write_json(
                run_root / "challenge" / "manifest.json",
                {
                    "baseline_provenance": {
                        "planner_backend": "gemini",
                        "llm_model": "gemini-3.1-pro-preview",
                        "backend": "openmodelica_docker",
                    }
                },
            )
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "finalize-run",
                    "--out-dir",
                    str(out_dir),
                    "--run-root",
                    str(run_root),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            realism_summary = json.loads((run_root / "realism_internal_summary.json").read_text(encoding="utf-8"))
            repair_queue = json.loads((run_root / "repair_queue_summary.json").read_text(encoding="utf-8"))
            patch_plan = json.loads((run_root / "wave1_patch_plan_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final_summary.get("status"), "BLOCKED")
            self.assertEqual(final_summary.get("primary_reason"), "baseline_execution_failed")
            self.assertEqual(final_summary.get("taxonomy_alignment_status"), "INCOMPLETE")
            self.assertEqual(realism_summary.get("status"), "BLOCKED")
            self.assertIn("l3_run_results_missing", realism_summary.get("reasons") or [])
            self.assertEqual(repair_queue.get("status"), "BLOCKED")
            self.assertEqual(patch_plan.get("status"), "BLOCKED")

    def test_resume_run_auto_backfills_missing_stages_and_refreshes_bundle(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        report_script = repo_root / "scripts" / "report_agent_modelica_l4_realism_run_status_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            _build_legacy_artifacts(out_dir)
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "adopt-legacy",
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )

            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RESUME_RUN_ID": "legacy_adopted_v1",
                "GATEFORGE_AGENT_L4_REALISM_RESUME_STAGES": "auto",
                "GATEFORGE_AGENT_L4_REALISM_SCALES": "small,medium",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND": "rule",
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND": "rule",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_PLANNER_BACKEND": "rule",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MIN_OFF_SUCCESS_PCT": "0",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MAX_OFF_SUCCESS_PCT": "100",
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
            }
            proc = self._run_resume_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            run_root = out_dir / "runs" / "legacy_adopted_v1"
            run_status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            evidence_summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            realism_summary = json.loads((run_root / "realism_internal_summary.json").read_text(encoding="utf-8"))
            main_l5 = json.loads((run_root / "main_l5" / "l5_eval_summary.json").read_text(encoding="utf-8"))
            night_l5 = json.loads((run_root / "night_l5" / "l5_eval_summary.json").read_text(encoding="utf-8"))
            night_sweep = json.loads((run_root / "night_sweep" / "summary.json").read_text(encoding="utf-8"))

            self.assertTrue(bool(run_status.get("finalized")))
            self.assertEqual(evidence_summary.get("status"), "PASS")
            self.assertNotEqual(final_summary.get("primary_reason"), "downstream_evidence_incomplete")
            self.assertNotEqual(final_summary.get("taxonomy_alignment_status"), "INCOMPLETE")
            self.assertTrue(bool(realism_summary))
            self.assertTrue(bool(main_l5))
            self.assertTrue(bool(night_l5))
            self.assertTrue(bool(night_sweep))
            self.assertFalse(bool((json.loads((run_root / "stages" / "main_sweep" / "stage_status.json").read_text(encoding="utf-8")).get("details") or {}).get("resume_attempts")))

            report = subprocess.run(
                ["bash", str(report_script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **env,
                    "GATEFORGE_AGENT_L4_REALISM_RUN_ID": "legacy_adopted_v1",
                },
                timeout=120,
            )
            self.assertEqual(report.returncode, 0, msg=report.stderr or report.stdout)
            report_payload = json.loads(report.stdout.strip().splitlines()[-1])
            self.assertFalse(bool(report_payload.get("resume_recommended")))
            self.assertEqual(report_payload.get("next_resume_stages"), [])

    def test_resume_run_without_explicit_run_id_uses_latest_run(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            _build_legacy_artifacts(out_dir)
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "adopt-legacy",
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            proc = self._run_resume_script(
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_L4_REALISM_RESUME_STAGES": "auto",
                    "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                    "GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND": "rule",
                    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND": "rule",
                    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                    "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                    "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                    "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                    "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                    "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                    "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                    "GATEFORGE_AGENT_L4_REALISM_SCALES": "small,medium",
                },
                repo_root=repo_root,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(payload.get("run_id"), "legacy_adopted_v1")

    def test_runtime_config_prefers_persisted_manifest_backends_for_resume(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "runs" / "resume_cfg01"
            (run_root / "challenge").mkdir(parents=True, exist_ok=True)
            _write_json(
                run_root / "run_manifest.json",
                {
                    "schema_version": "agent_modelica_realism_run_manifest_v1",
                    "run_id": "resume_cfg01",
                    "out_dir": str(Path(d)),
                    "run_root": str(run_root),
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "runtime_config": {
                        "scales": "small,medium",
                        "profiles": "score_v1",
                        "backend": "openmodelica_docker",
                        "docker_image": "openmodelica/openmodelica:v1.26.1-minimal",
                        "challenge_planner_backend": "gemini",
                        "main_planner_backend": "gemini",
                        "night_planner_backend": "gemini",
                        "l4_policy_backend": "gemini",
                        "main_gate_mode": "strict",
                        "night_gate_mode": "observe",
                    },
                },
            )
            _write_json(
                run_root / "challenge" / "frozen_summary.json",
                {
                    "schema_version": "agent_modelica_l4_challenge_pack_v0",
                    "status": "PASS",
                    "baseline_off_success_at_k_pct": 88.89,
                    "baseline_meets_minimum": True,
                    "baseline_has_headroom": True,
                    "baseline_provenance": {
                        "planner_backend": "gemini",
                        "llm_model": "gemini-3.1-pro-preview",
                    },
                },
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND": "",
                    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND": "",
                    "GATEFORGE_AGENT_L4_UPLIFT_L4_POLICY_BACKEND": "",
                },
                clear=False,
            ):
                cfg = _runtime_config(run_root)
            self.assertEqual(cfg.get("main_planner_backend"), "gemini")
            self.assertEqual(cfg.get("night_planner_backend"), "gemini")
            self.assertEqual(cfg.get("l4_policy_backend"), "gemini")

    def test_runtime_config_defaults_to_auto_when_no_planner_backend_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "runs" / "resume_cfg_auto01"
            (run_root / "challenge").mkdir(parents=True, exist_ok=True)
            _write_json(
                run_root / "challenge" / "frozen_summary.json",
                {
                    "schema_version": "agent_modelica_l4_challenge_pack_v0",
                    "status": "PASS",
                    "baseline_off_success_at_k_pct": 70.0,
                    "baseline_meets_minimum": True,
                    "baseline_has_headroom": True,
                },
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_PLANNER_BACKEND": "",
                    "GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND": "",
                    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND": "",
                },
                clear=False,
            ):
                cfg = _runtime_config(run_root)
            self.assertEqual(cfg.get("challenge_planner_backend"), "auto")
            self.assertEqual(cfg.get("main_planner_backend"), "rule")
            self.assertEqual(cfg.get("night_planner_backend"), "auto")

    def test_plain_realism_run_infers_and_propagates_gemini_backend_from_env(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_l4_realism_evidence_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_dir = root / "out"
            _build_taskset(taskset)
            _write_realism_manifest(
                taskset,
                builder_sha=hashlib.sha256((repo_root / "gateforge" / "agent_modelica_electrical_mutant_taskset_v0.py").read_bytes()).hexdigest(),
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET": str(taskset),
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GOOGLE_API_KEY": "test-key",
                "LLM_MODEL": "gemini-3.1-pro-preview",
                "GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MIN_OFF_SUCCESS_PCT": "0",
                "GATEFORGE_AGENT_L4_UPLIFT_TARGET_MAX_OFF_SUCCESS_PCT": "100",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            runs_dir = out_dir / "runs"
            run_root = sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)[-1]
            manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
            cfg = manifest.get("runtime_config") if isinstance(manifest.get("runtime_config"), dict) else {}
            self.assertEqual(cfg.get("challenge_planner_backend"), "gemini")
            self.assertEqual(cfg.get("main_planner_backend"), "gemini")
            self.assertEqual(cfg.get("night_planner_backend"), "gemini")
            self.assertEqual(cfg.get("l4_policy_backend"), "gemini")
            main_sweep = json.loads((run_root / "main_sweep" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(str(main_sweep.get("planner_backend") or ""), "gemini")
            self.assertEqual(str(main_sweep.get("l4_policy_backend") or ""), "gemini")

    def test_resume_run_auto_skips_night_stages_for_lean_runtime(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            run_root = out_dir / "runs" / "lean_resume01"
            (run_root / "challenge").mkdir(parents=True, exist_ok=True)
            _build_taskset(run_root / "challenge" / "taskset_frozen.json")
            _write_json(
                run_root / "run_manifest.json",
                {
                    "schema_version": "agent_modelica_realism_run_manifest_v1",
                    "run_id": "lean_resume01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "runtime_config": {
                        "scales": "small,medium",
                        "profiles": "score_v1",
                        "backend": "mock",
                        "challenge_planner_backend": "gemini",
                        "main_planner_backend": "gemini",
                        "night_planner_backend": "gemini",
                        "realism_mode": "lean",
                        "night_enabled": "0",
                        "main_gate_mode": "strict",
                        "night_gate_mode": "observe",
                    },
                },
            )
            _write_json(
                run_root / "run_status.json",
                {
                    "schema_version": "agent_modelica_realism_run_status_v1",
                    "run_id": "lean_resume01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "status": "RUNNING",
                    "current_stage": "challenge",
                    "finalized": False,
                    "latest_updated": False,
                    "stages": {},
                },
            )
            _write_json(
                run_root / "challenge" / "frozen_summary.json",
                {
                    "schema_version": "agent_modelica_l4_challenge_pack_v0",
                    "status": "PASS",
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "baseline_off_success_at_k_pct": 88.89,
                    "baseline_off_record_count": 6,
                    "baseline_execution_valid": True,
                    "baseline_meets_minimum": True,
                    "baseline_has_headroom": True,
                    "counts_by_failure_type": {
                        "underconstrained_system": 2,
                        "connector_mismatch": 2,
                        "initialization_infeasible": 2,
                    },
                    "counts_by_category": {
                        "topology_wiring": 4,
                        "initialization": 2,
                    },
                },
            )
            _write_json(
                run_root / "main_sweep" / "summary.json",
                {
                    "status": "FAIL",
                    "recommended_profile": "",
                    "profiles": ["score_v1"],
                    "reasons": ["no_profile_passed"],
                },
            )
            env = {
                **os.environ,
                "GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_REALISM_RESUME_RUN_ID": "lean_resume01",
                "GATEFORGE_AGENT_L4_REALISM_RESUME_STAGES": "auto",
                "GATEFORGE_AGENT_L4_UPLIFT_BACKEND": "mock",
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD": _cmd_pass(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD": _cmd_l4_switch(),
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS": "1",
                "GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC": "20",
                "GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS": "1",
            }
            proc = self._run_resume_script(env=env, repo_root=repo_root)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            night_sweep_stage = json.loads((run_root / "stages" / "night_sweep" / "stage_status.json").read_text(encoding="utf-8"))
            night_l5_stage = json.loads((run_root / "stages" / "night_l5" / "stage_status.json").read_text(encoding="utf-8"))
            self.assertEqual(night_sweep_stage.get("status"), "SKIPPED")
            self.assertEqual(night_l5_stage.get("status"), "SKIPPED")
            self.assertTrue((run_root / "night_sweep" / "summary.json").exists())
            self.assertTrue((run_root / "night_l5" / "l5_eval_summary.json").exists())

    def test_finalize_run_refreshes_lean_bundle_without_night_missing_artifacts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            run_root = out_dir / "runs" / "lean_refresh01"
            run_root.mkdir(parents=True, exist_ok=True)
            _write_json(
                run_root / "run_manifest.json",
                {
                    "run_id": "lean_refresh01",
                    "runtime_config": {
                        "realism_mode": "lean",
                        "night_enabled": "0",
                        "main_profile": "score_v1",
                        "min_delta_success_pp": "5",
                        "absolute_success_target_pct": "85",
                        "non_regression_tolerance_pp": "0",
                        "max_regression_worsen_pp": "2",
                        "max_physics_worsen_pp": "2",
                    },
                },
            )
            _write_json(run_root / "challenge" / "frozen_summary.json", {"status": "PASS", "baseline_meets_minimum": True, "baseline_has_headroom": False, "baseline_off_success_at_k_pct": 100.0})
            _write_json(run_root / "main_sweep" / "summary.json", {"status": "FAIL", "planner_backend": "gemini"})
            _write_json(run_root / "main_l5" / "l5_eval_summary.json", {"status": "FAIL", "gate_result": "FAIL", "acceptance_mode": "absolute_non_regression", "success_at_k_pct": 0.0, "non_regression_ok": False, "l4_primary_reason": "none"})
            _write_json(run_root / "main_l5" / "l5_weekly_metrics.json", {"recommendation": "hold", "recommendation_reason": "insufficient_consecutive_history"})
            _write_json(run_root / "night_sweep" / "summary.json", {})
            _write_json(run_root / "night_l5" / "l5_eval_summary.json", {})
            _write_json(run_root / "night_l5" / "l5_weekly_metrics.json", {})
            _write_json(run_root / "summary.json", {"status": "FAIL", "primary_reason": "missing_artifacts", "reasons": ["missing_night_sweep_summary"]})
            _write_json(run_root / "realism_internal_summary.json", {"status": "BLOCKED", "reasons": ["l3_run_results_missing"]})
            _write_json(run_root / "run_status.json", {"run_id": "lean_refresh01", "status": "RUNNING", "current_stage": "finalize"})
            for stage in ("challenge", "main_sweep", "night_sweep", "main_l5", "night_l5"):
                _write_json(run_root / "stages" / stage / "stage_status.json", {"status": "PASS", "exit_code": 0, "complete": True})

            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "finalize-run",
                    "--out-dir",
                    str(out_dir),
                    "--run-root",
                    str(run_root),
                    "--update-latest",
                    "0",
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            evidence_summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            decision_summary = json.loads((run_root / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertFalse(bool(evidence_summary.get("night_enabled")))
            self.assertNotIn("missing_night_sweep_summary", set(evidence_summary.get("reasons") or []))
            self.assertNotIn("missing_night_l5_eval_summary", set(evidence_summary.get("reasons") or []))
            self.assertFalse(bool(decision_summary.get("night_enabled")))
            self.assertNotIn("missing_artifacts", set(decision_summary.get("reasons") or []))

    def test_resume_run_force_rerun_completed_clears_stale_downstream_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            run_root = out_dir / "runs" / "rerun_clean01"
            (run_root / "challenge").mkdir(parents=True, exist_ok=True)
            _build_taskset(run_root / "challenge" / "taskset_frozen.json")
            _write_json(
                run_root / "run_manifest.json",
                {
                    "schema_version": "agent_modelica_realism_run_manifest_v1",
                    "run_id": "rerun_clean01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "runtime_config": {
                        "scales": "small,medium",
                        "profiles": "score_v1",
                        "backend": "mock",
                        "challenge_planner_backend": "gemini",
                        "main_planner_backend": "gemini",
                        "night_planner_backend": "gemini",
                        "realism_mode": "lean",
                        "night_enabled": "0",
                        "main_gate_mode": "strict",
                        "night_gate_mode": "observe",
                    },
                },
            )
            _write_json(
                run_root / "run_status.json",
                {
                    "schema_version": "agent_modelica_realism_run_status_v1",
                    "run_id": "rerun_clean01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "status": "NEEDS_REVIEW",
                    "current_stage": "finalize",
                    "finalized": True,
                    "latest_updated": True,
                    "stages": {
                        "challenge": {"status": "PASS"},
                        "main_sweep": {"status": "PASS"},
                        "main_l5": {"status": "FAIL"},
                        "realism_summary": {"status": "PASS"},
                        "finalize": {"status": "PASS"},
                    },
                },
            )
            _write_json(
                run_root / "challenge" / "frozen_summary.json",
                {
                    "schema_version": "agent_modelica_l4_challenge_pack_v0",
                    "status": "PASS",
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "baseline_off_success_at_k_pct": 88.89,
                    "baseline_off_record_count": 6,
                    "baseline_execution_valid": True,
                    "baseline_meets_minimum": True,
                    "baseline_has_headroom": True,
                },
            )
            _write_json(run_root / "main_sweep" / "summary.json", {"status": "PASS", "profiles": {"score_v1": {}}})
            _write_json(run_root / "main_l5" / "l5_eval_summary.json", {"status": "FAIL"})
            _write_json(run_root / "realism_internal_summary.json", {"status": "FAIL"})
            _write_json(run_root / "repair_queue_summary.json", {"status": "PASS"})
            _write_json(run_root / "wave1_patch_plan_summary.json", {"status": "PASS"})
            _write_json(run_root / "final_run_summary.json", {"status": "NEEDS_REVIEW"})
            _write_json(run_root / "summary.json", {"status": "PASS"})
            for stage in ("main_l5", "realism_summary", "finalize"):
                (run_root / "stages" / stage).mkdir(parents=True, exist_ok=True)
                _write_json(run_root / "stages" / stage / "stage_status.json", {"stage": stage, "status": "PASS"})

            calls: list[str] = []

            def _fake_run_resumable_stage(
                run_root_arg: Path,
                stage: str,
                cfg: dict,
                *,
                restart_live_budget_window: bool = False,
            ) -> int:
                calls.append(stage)
                summary_path = {
                    "main_l5": run_root_arg / "main_l5" / "l5_eval_summary.json",
                    "realism_summary": run_root_arg / "realism_internal_summary.json",
                }.get(stage, run_root_arg / "final_run_summary.json")
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                _write_json(summary_path, {"status": "PASS", "stage": stage})
                realism_lifecycle.stage_update(
                    run_root=str(run_root_arg),
                    stage=stage,
                    status="PASS",
                    exit_code=0,
                    summary_path=str(summary_path),
                    details={"mocked": True},
                )
                return 0

            with mock.patch.object(realism_lifecycle, "_run_resumable_stage", side_effect=_fake_run_resumable_stage), mock.patch.object(
                realism_lifecycle,
                "_refresh_decision_and_bundle",
                return_value={"decision_rc": 0, "bundle_rc": 0},
            ), mock.patch.object(
                realism_lifecycle,
                "finalize_run",
                return_value={"status": "PASS"},
            ), mock.patch.object(
                realism_lifecycle,
                "report_run",
                return_value={"status": "RUNNING", "run_id": "rerun_clean01"},
            ):
                payload = realism_lifecycle.resume_run(
                    out_dir=str(out_dir),
                    run_id="rerun_clean01",
                    stages="main_l5,realism_summary,finalize",
                    update_latest=False,
                    force_rerun_completed=True,
                )

            self.assertEqual(payload.get("run_id"), "rerun_clean01")
            self.assertEqual(calls, ["main_l5", "realism_summary"])
            self.assertFalse((run_root / "final_run_summary.json").exists())
            self.assertFalse((run_root / "repair_queue_summary.json").exists())
            stage_status = json.loads((run_root / "stages" / "main_l5" / "stage_status.json").read_text(encoding="utf-8"))
            self.assertEqual(stage_status.get("status"), "PASS")
            run_status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
            self.assertFalse(bool(run_status.get("finalized")))
            self.assertEqual(run_status.get("status"), "RUNNING")

    def test_run_resumable_main_l5_propagates_live_request_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            run_root = out_dir / "runs" / "ledger_resume01"
            (run_root / "challenge").mkdir(parents=True, exist_ok=True)
            _build_taskset(run_root / "challenge" / "taskset_frozen.json")
            _write_json(
                run_root / "run_manifest.json",
                {
                    "schema_version": "agent_modelica_realism_run_manifest_v1",
                    "run_id": "ledger_resume01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "runtime_config": {
                        "scales": "small,medium",
                        "profiles": "score_v1",
                        "backend": "openmodelica_docker",
                        "docker_image": "openmodelica/openmodelica:v1.26.1-minimal",
                        "challenge_planner_backend": "gemini",
                        "main_planner_backend": "gemini",
                        "night_planner_backend": "gemini",
                        "realism_mode": "lean",
                        "night_enabled": "0",
                        "main_gate_mode": "strict",
                        "night_gate_mode": "observe",
                    },
                },
            )
            _write_json(
                run_root / "run_status.json",
                {
                    "schema_version": "agent_modelica_realism_run_status_v1",
                    "run_id": "ledger_resume01",
                    "out_dir": str(out_dir),
                    "run_root": str(run_root),
                    "status": "RUNNING",
                    "current_stage": "main_l5",
                    "finalized": False,
                    "latest_updated": False,
                    "stages": {},
                },
            )

            cfg = realism_lifecycle._runtime_config(run_root)
            captured: dict[str, str] = {}

            def _fake_run_shell_script(script_name: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
                captured["script_name"] = script_name
                captured.update(env)
                return subprocess.CompletedProcess(args=[script_name], returncode=0, stdout="", stderr="")

            with mock.patch.object(realism_lifecycle, "_run_shell_script", side_effect=_fake_run_shell_script):
                rc = realism_lifecycle._run_resumable_stage(run_root, "main_l5", cfg)

            self.assertEqual(rc, 0)
            self.assertEqual(captured.get("script_name"), "run_agent_modelica_l5_eval_v1.sh")
            self.assertEqual(
                captured.get("GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH"),
                str(run_root / "private" / "live_request_ledger.json"),
            )
            self.assertEqual(captured.get("GATEFORGE_AGENT_LIVE_REQUEST_STAGE"), "main_l5")


if __name__ == "__main__":
    unittest.main()
