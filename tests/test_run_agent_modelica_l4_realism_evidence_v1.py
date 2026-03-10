import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


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
            self.assertEqual(final_summary.get("status"), "BLOCKED")
            self.assertEqual(final_summary.get("primary_reason"), "environment_preflight_failed")
            self.assertTrue(bool(run_status.get("finalized")))
            self.assertFalse((out_dir / "latest_summary.json").exists())
            self.assertFalse((out_dir / "latest_run.json").exists())

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
            latest_run = json.loads((out_dir / "latest_run.json").read_text(encoding="utf-8"))
            latest_summary = json.loads((out_dir / "latest_summary.json").read_text(encoding="utf-8"))
            latest_realism = json.loads((out_dir / "latest_realism_internal_summary.json").read_text(encoding="utf-8"))
            challenge = json.loads((run_root / "challenge" / "frozen_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(final_summary.get("run_id"), "success01")
            self.assertEqual(final_summary.get("baseline_state"), "baseline_saturated")
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
            self.assertEqual(
                payload.get("next_resume_stages"),
                ["night_sweep", "main_l5", "night_l5", "realism_summary"],
            )
            self.assertEqual(payload.get("resume_blockers"), [])

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


if __name__ == "__main__":
    unittest.main()
