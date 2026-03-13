from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_realism_run_lifecycle_v1"
RUN_STATUS_SCHEMA_VERSION = "agent_modelica_realism_run_status_v1"
RUN_MANIFEST_SCHEMA_VERSION = "agent_modelica_realism_run_manifest_v1"
FINAL_RUN_SUMMARY_SCHEMA_VERSION = "agent_modelica_realism_final_run_summary_v1"
STAGE_STATUS_SCHEMA_VERSION = "agent_modelica_realism_stage_status_v1"
LATEST_RUN_SCHEMA_VERSION = "agent_modelica_realism_latest_run_v1"
LEGACY_RUN_ID = "legacy_adopted_v1"
STAGE_ORDER = [
    "preflight",
    "challenge",
    "main_sweep",
    "night_sweep",
    "main_l5",
    "night_l5",
    "realism_summary",
    "finalize",
]
TERMINAL_STAGE_STATUSES = {"PASS", "FAIL", "BLOCKED", "SKIPPED", "MISSING"}
RESUMABLE_STAGE_ORDER = [
    "challenge",
    "main_sweep",
    "night_sweep",
    "main_l5",
    "night_l5",
    "realism_summary",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _bool_env(value: str | None, default: bool = True) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _safe_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _nonempty_dict(payload: dict) -> bool:
    return isinstance(payload, dict) and bool(payload)


def _stage_status_path(run_root: Path, stage: str) -> Path:
    return run_root / "stages" / stage / "stage_status.json"


def _stage_status_md_path(run_root: Path, stage: str) -> Path:
    return run_root / "stages" / stage / "stage_status.md"


def _run_status_path(run_root: Path) -> Path:
    return run_root / "run_status.json"


def _run_manifest_path(run_root: Path) -> Path:
    return run_root / "run_manifest.json"


def _final_summary_path(run_root: Path) -> Path:
    return run_root / "final_run_summary.json"


def _final_summary_md_path(run_root: Path) -> Path:
    return run_root / "final_run_summary.md"


def _legacy_artifact_paths(root: Path) -> dict[str, Path]:
    return {
        "summary": root / "summary.json",
        "decision": root / "decision_summary.json",
        "decision_md": root / "decision_summary.md",
        "preflight": root / "environment_preflight_summary.json",
        "preflight_md": root / "environment_preflight_summary.md",
        "challenge_dir": root / "challenge",
        "challenge_summary": root / "challenge" / "frozen_summary.json",
        "main_sweep_dir": root / "main_sweep",
        "main_sweep_summary": root / "main_sweep" / "summary.json",
        "night_sweep_dir": root / "night_sweep",
        "night_sweep_summary": root / "night_sweep" / "summary.json",
        "main_l5_dir": root / "main_l5",
        "main_l5_summary": root / "main_l5" / "l5_eval_summary.json",
        "night_l5_dir": root / "night_l5",
        "night_l5_summary": root / "night_l5" / "l5_eval_summary.json",
    }


def _challenge_complete(payload: dict) -> bool:
    if not _nonempty_dict(payload):
        return False
    return _safe_float(payload.get("baseline_off_success_at_k_pct")) is not None


def _sweep_complete(payload: dict) -> bool:
    if not _nonempty_dict(payload):
        return False
    if payload.get("profiles") or payload.get("profile_summaries"):
        return True
    return any(key in payload for key in ("recommended_profile", "acceptance", "delta_success_at_k_pp", "status"))


def _l5_complete(payload: dict) -> bool:
    if not _nonempty_dict(payload):
        return False
    return any(
        key in payload
        for key in (
            "gate_result",
            "success_at_k_pct",
            "category_breakdown_on",
            "failure_type_breakdown_on",
            "record_count",
            "status",
        )
    )


def _read_run_status(run_root: Path) -> dict:
    payload = _load_json(_run_status_path(run_root))
    if payload:
        return payload
    return {
        "schema_version": RUN_STATUS_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "updated_at_utc": _utc_now(),
        "run_id": run_root.name,
        "run_root": str(run_root),
        "status": "RUNNING",
        "current_stage": "",
        "finalized": False,
        "stages": {},
    }


def _write_run_status_md(run_root: Path, run_status: dict) -> None:
    _write_md(
        run_root / "run_status.md",
        [
            "# Agent Modelica Realism Run Status",
            "",
            f"- run_id: `{run_status.get('run_id')}`",
            f"- status: `{run_status.get('status')}`",
            f"- current_stage: `{run_status.get('current_stage')}`",
            f"- finalized: `{run_status.get('finalized')}`",
            f"- latest_updated: `{run_status.get('latest_updated')}`",
        ],
    )


def init_run(
    *,
    out_dir: str,
    run_root: str,
    run_id: str,
    pack_id: str,
    pack_version: str,
    pack_track: str,
    acceptance_scope: str,
    base_taskset: str,
    lock_path: str,
    update_latest: bool,
    runtime_config: dict | None = None,
) -> dict:
    root = Path(run_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "run_id": run_id,
        "out_dir": str(Path(out_dir)),
        "run_root": str(root),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_track": pack_track,
        "acceptance_scope": acceptance_scope,
        "base_taskset": base_taskset,
        "lock_path": lock_path,
        "update_latest": bool(update_latest),
        "runtime_config": runtime_config if isinstance(runtime_config, dict) else {},
    }
    run_status = {
        "schema_version": RUN_STATUS_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "updated_at_utc": _utc_now(),
        "run_id": run_id,
        "out_dir": str(Path(out_dir)),
        "run_root": str(root),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "pack_track": pack_track,
        "acceptance_scope": acceptance_scope,
        "base_taskset": base_taskset,
        "lock_path": lock_path,
        "status": "RUNNING",
        "current_stage": "init",
        "finalized": False,
        "final_run_summary_path": "",
        "latest_updated": False,
        "stages": {},
    }
    _write_json(_run_manifest_path(root), manifest)
    _write_json(_run_status_path(root), run_status)
    _write_run_status_md(root, run_status)
    return run_status


def stage_update(
    *,
    run_root: str,
    stage: str,
    status: str,
    exit_code: int | None = None,
    summary_path: str = "",
    details: dict | None = None,
) -> dict:
    root = Path(run_root)
    payload = _load_json(_stage_status_path(root, stage))
    prior_details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    started_at = str(payload.get("started_at_utc") or _utc_now())
    if str(status).upper() == "RUNNING":
        started_at = _utc_now()
        finished_at = ""
    else:
        finished_at = _utc_now()
    stage_payload = {
        "schema_version": STAGE_STATUS_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "stage": stage,
        "status": status,
        "exit_code": exit_code,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "summary_path": summary_path,
        "details": {**prior_details, **(details or {})},
    }
    _write_json(_stage_status_path(root, stage), stage_payload)
    _write_md(
        _stage_status_md_path(root, stage),
        [
            f"# Realism Stage: {stage}",
            "",
            f"- status: `{status}`",
            f"- exit_code: `{exit_code}`",
            f"- summary_path: `{summary_path}`",
        ],
    )

    run_status = _read_run_status(root)
    run_status["updated_at_utc"] = _utc_now()
    run_status["current_stage"] = stage
    if str(status).upper() == "BLOCKED":
        run_status["status"] = "BLOCKED"
    elif not bool(run_status.get("finalized")):
        run_status["status"] = "RUNNING"
    stages = run_status.get("stages") if isinstance(run_status.get("stages"), dict) else {}
    stages[stage] = {
        "status": status,
        "exit_code": exit_code,
        "summary_path": summary_path,
        "stage_status_path": str(_stage_status_path(root, stage)),
    }
    run_status["stages"] = stages
    _write_json(_run_status_path(root), run_status)
    _write_run_status_md(root, run_status)
    return stage_payload


def _stage_payload_complete(stage: str, summary_path: Path, payload: dict) -> bool:
    if stage == "preflight":
        if _nonempty_dict(payload):
            return True
        return not summary_path.exists()
    if stage == "challenge":
        return _challenge_complete(payload)
    if stage in {"main_sweep", "night_sweep"}:
        return _sweep_complete(payload)
    if stage in {"main_l5", "night_l5"}:
        return _l5_complete(payload)
    if stage == "realism_summary":
        return _nonempty_dict(payload)
    if stage == "finalize":
        return _nonempty_dict(payload)
    return False


def _scoped_stage_summary_path(root: Path, stage: str) -> Path:
    mapping = {
        "preflight": root / "environment_preflight_summary.json",
        "challenge": root / "challenge" / "frozen_summary.json",
        "main_sweep": root / "main_sweep" / "summary.json",
        "night_sweep": root / "night_sweep" / "summary.json",
        "main_l5": root / "main_l5" / "l5_eval_summary.json",
        "night_l5": root / "night_l5" / "l5_eval_summary.json",
        "realism_summary": root / "realism_internal_summary.json",
        "finalize": root / "final_run_summary.json",
    }
    return mapping[stage]


def _infer_scoped_stage_states(root: Path) -> dict[str, dict]:
    run_status = _read_run_status(root)
    run_stages = run_status.get("stages") if isinstance(run_status.get("stages"), dict) else {}
    states: dict[str, dict] = {}
    for stage in STAGE_ORDER:
        stage_status = _load_json(_stage_status_path(root, stage))
        summary_path = _scoped_stage_summary_path(root, stage)
        summary_payload = _load_json(summary_path)
        explicit_status = str(stage_status.get("status") or (run_stages.get(stage) or {}).get("status") or "").upper()
        complete = _stage_payload_complete(stage, summary_path, summary_payload)
        status = explicit_status or ("PASS" if complete else "")
        if not status and summary_path.exists() and not complete:
            status = "RUNNING"
        states[stage] = {
            "status": status,
            "complete": complete,
            "summary_path": str(summary_path),
            "summary_exists": summary_path.exists(),
        }
    return states


def _legacy_stage_states(root: Path) -> dict[str, dict]:
    paths = _legacy_artifact_paths(root)
    preflight = _load_json(paths["preflight"])
    challenge = _load_json(paths["challenge_summary"])
    main_sweep = _load_json(paths["main_sweep_summary"])
    night_sweep = _load_json(paths["night_sweep_summary"])
    main_l5 = _load_json(paths["main_l5_summary"])
    night_l5 = _load_json(paths["night_l5_summary"])
    summary = _load_json(paths["summary"])

    preflight_complete = True if _challenge_complete(challenge) or _sweep_complete(main_sweep) or _l5_complete(main_l5) else _nonempty_dict(preflight)
    preflight_status = ""
    if str(preflight.get("status") or "").upper() == "BLOCKED":
        preflight_status = "BLOCKED"
        preflight_complete = True
    elif preflight_complete:
        preflight_status = "PASS"

    states = {
        "preflight": {
            "status": preflight_status,
            "complete": preflight_complete,
            "summary_path": str(paths["preflight"]),
            "summary_exists": paths["preflight"].exists(),
        },
        "challenge": {
            "status": str(challenge.get("status") or ("PASS" if _challenge_complete(challenge) else "")).upper(),
            "complete": _challenge_complete(challenge),
            "summary_path": str(paths["challenge_summary"]),
            "summary_exists": paths["challenge_summary"].exists(),
        },
        "main_sweep": {
            "status": str(main_sweep.get("status") or ("PASS" if _sweep_complete(main_sweep) else "")).upper(),
            "complete": _sweep_complete(main_sweep),
            "summary_path": str(paths["main_sweep_summary"]),
            "summary_exists": paths["main_sweep_summary"].exists(),
        },
        "night_sweep": {
            "status": str(night_sweep.get("status") or ("PASS" if _sweep_complete(night_sweep) else "")).upper(),
            "complete": _sweep_complete(night_sweep),
            "summary_path": str(paths["night_sweep_summary"]),
            "summary_exists": paths["night_sweep_summary"].exists(),
        },
        "main_l5": {
            "status": str(main_l5.get("status") or ("PASS" if _l5_complete(main_l5) else "")).upper(),
            "complete": _l5_complete(main_l5),
            "summary_path": str(paths["main_l5_summary"]),
            "summary_exists": paths["main_l5_summary"].exists(),
        },
        "night_l5": {
            "status": str(night_l5.get("status") or ("PASS" if _l5_complete(night_l5) else "")).upper(),
            "complete": _l5_complete(night_l5),
            "summary_path": str(paths["night_l5_summary"]),
            "summary_exists": paths["night_l5_summary"].exists(),
        },
        "realism_summary": {
            "status": "",
            "complete": False,
            "summary_path": str(root / "realism_internal_summary.json"),
            "summary_exists": (root / "realism_internal_summary.json").exists(),
        },
        "finalize": {
            "status": "",
            "complete": False,
            "summary_path": str(root / "final_run_summary.json"),
            "summary_exists": False,
        },
    }
    if str(summary.get("status") or "").upper() == "BLOCKED" and not states["challenge"]["complete"]:
        states["preflight"]["status"] = "BLOCKED"
        states["preflight"]["complete"] = True
    return states


def _discover_legacy_active_pid(out_root: Path) -> int | None:
    sidecar = _load_json(out_root / ".legacy_active_pid.json")
    hinted_pid = _safe_int(sidecar.get("pid"))
    if _pid_alive(hinted_pid):
        return hinted_pid
    try:
        proc = subprocess.run(
            ["ps", "-ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return None
    matches: list[tuple[int, str]] = []
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) < 2:
            continue
        pid = _safe_int(parts[0])
        command = parts[1]
        if (
            pid
            and pid != os.getpid()
            and (
                "agent_modelica_l4_realism_evidence_v1.sh" in command
                or "agent_modelica_run_contract_v1" in command
                or "agent_modelica_live_executor_" in command
            )
        ):
            matches.append((pid, command))
    preferred = [pid for pid, command in matches if str(out_root) in command]
    if preferred:
        return preferred[0]
    if len(matches) == 1:
        return matches[0][0]
    return None


def _active_scoped_pid(root: Path) -> int | None:
    manifest = _load_json(_run_manifest_path(root))
    lock_path = Path(str(manifest.get("lock_path") or ""))
    if not lock_path.exists():
        return None
    lock = _load_json(lock_path)
    lock_run_root = str(lock.get("run_root") or "")
    pid = _safe_int(lock.get("pid"))
    if lock_run_root == str(root) and _pid_alive(pid):
        return pid
    return None


def _current_stage_from_states(states: dict[str, dict], finalized: bool) -> str:
    if finalized:
        return "finalize"
    for stage in STAGE_ORDER:
        row = states.get(stage) if isinstance(states.get(stage), dict) else {}
        status = str(row.get("status") or "").upper()
        if not bool(row.get("complete")) and status != "SKIPPED":
            return stage
    return "finalize"


def _completed_and_missing_stages(states: dict[str, dict]) -> tuple[list[str], list[str]]:
    def _done(row: dict) -> bool:
        status = str(row.get("status") or "").upper()
        return bool(row.get("complete")) or status == "SKIPPED"

    completed = [stage for stage in STAGE_ORDER if _done(states.get(stage) or {})]
    missing = [stage for stage in STAGE_ORDER if not _done(states.get(stage) or {}) and stage != "finalize"]
    return completed, missing


def _night_enabled(cfg: dict) -> bool:
    return _bool_env(str(cfg.get("night_enabled") or cfg.get("realism_mode") != "lean"), default=True)


def _auto_resume_stages(states: dict[str, dict], cfg: dict | None = None) -> list[str]:
    night_enabled = True if cfg is None else _night_enabled(cfg)
    return [
        stage
        for stage in RESUMABLE_STAGE_ORDER
        if not bool((states.get(stage) or {}).get("complete"))
        and str((states.get(stage) or {}).get("status") or "").upper() != "SKIPPED"
        and (night_enabled or stage not in {"night_sweep", "night_l5"})
    ]


def _resume_blockers(run_mode: str, *, active_pid: int | None, states: dict[str, dict]) -> list[str]:
    blockers: list[str] = []
    if run_mode == "legacy":
        blockers.append("legacy_run_requires_adoption")
    if active_pid:
        blockers.append("active_run_in_progress")
    if not bool((states.get("challenge") or {}).get("complete")) and str((states.get("preflight") or {}).get("status") or "").upper() == "BLOCKED":
        blockers.append("environment_preflight_blocked")
    return blockers


def _set_run_resuming(run_root: Path, stage: str) -> dict:
    run_status = _read_run_status(run_root)
    run_status["updated_at_utc"] = _utc_now()
    run_status["status"] = "RUNNING"
    run_status["current_stage"] = stage
    run_status["finalized"] = False
    run_status["latest_updated"] = False
    _write_json(_run_status_path(run_root), run_status)
    _write_run_status_md(run_root, run_status)
    return run_status


def _legacy_artifacts_exist(out_root: Path) -> bool:
    paths = _legacy_artifact_paths(out_root)
    return any(
        path.exists()
        for key, path in paths.items()
        if key.endswith("_dir") or key.endswith("_summary") or key in {"summary", "preflight"}
    )


def _maybe_refresh_realism_summary(run_root: Path) -> dict:
    from .agent_modelica_realism_summary_v1 import build_realism_summary_v1, _write_markdown

    evidence = _load_json(run_root / "summary.json")
    challenge = _load_json(run_root / "challenge" / "frozen_summary.json")
    manifest = _load_json(run_root / "challenge" / "manifest.json")
    taskset = _load_json(run_root / "challenge" / "taskset_frozen.json")
    l3_run = _load_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json")
    l3_quality = _load_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json")
    l4_ab = _load_json(run_root / "main_l5" / "l4" / "ab_compare_summary.json")
    l5_summary = _load_json(run_root / "main_l5" / "l5_eval_summary.json")
    if not (challenge and taskset):
        return {}
    realism = build_realism_summary_v1(
        evidence_summary=evidence,
        challenge_summary=challenge,
        challenge_manifest=manifest,
        taskset_payload=taskset,
        l3_run_results=l3_run,
        l3_quality_summary=l3_quality,
        l4_ab_compare_summary=l4_ab,
        l5_summary=l5_summary,
    )
    out_json = run_root / "realism_internal_summary.json"
    out_md = run_root / "realism_internal_summary.md"
    _write_json(out_json, realism)
    _write_markdown(str(out_md), realism)
    return realism


def _bootstrap_runtime_env() -> None:
    try:
        from .agent_modelica_live_executor_gemini_v1 import _bootstrap_env_from_repo
    except Exception:
        return
    _bootstrap_env_from_repo(
        allowed_keys={
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "LLM_MODEL",
            "GATEFORGE_GEMINI_MODEL",
            "GEMINI_MODEL",
        }
    )


def _runtime_config(run_root: Path) -> dict:
    manifest = _load_json(_run_manifest_path(run_root))
    persisted_runtime = manifest.get("runtime_config") if isinstance(manifest.get("runtime_config"), dict) else {}
    challenge = _load_json(run_root / "challenge" / "frozen_summary.json")
    main_sweep = _load_json(run_root / "main_sweep" / "summary.json")

    min_delta_success_pp = float(str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MIN_DELTA_SUCCESS_PP", "5")).strip() or 5.0)
    baseline_meets_minimum = challenge.get("baseline_meets_minimum")
    if baseline_meets_minimum is None:
        baseline_meets_minimum = challenge.get("baseline_in_target_range")
    baseline_has_headroom = challenge.get("baseline_has_headroom")
    if baseline_has_headroom is None:
        baseline = float(challenge.get("baseline_off_success_at_k_pct") or 0.0)
        baseline_has_headroom = baseline <= max(0.0, 100.0 - min_delta_success_pp)
    acceptance_mode = "absolute_non_regression" if bool(baseline_meets_minimum) and not bool(baseline_has_headroom) else "delta_uplift"

    llm_model = (
        str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LLM_MODEL") or "").strip()
        or str(os.environ.get("LLM_MODEL") or "").strip()
        or str(os.environ.get("GATEFORGE_GEMINI_MODEL") or "").strip()
        or str(os.environ.get("GEMINI_MODEL") or "").strip()
    )

    return {
        "repo_root": _repo_root(),
        "out_dir": str(run_root),
        "run_root": str(run_root),
        "taskset": str(run_root / "challenge" / "taskset_frozen.json"),
        "scales": str(
            persisted_runtime.get("scales")
            or os.environ.get("GATEFORGE_AGENT_L4_REALISM_SCALES")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_SCALES")
            or "small,medium"
        ),
        "profiles": str(
            persisted_runtime.get("profiles")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_PROFILES")
            or "score_v1,score_v1a,score_v1b,score_v1c"
        ),
        "backend": str(
            persisted_runtime.get("backend")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_BACKEND")
            or "openmodelica_docker"
        ),
        "docker_image": str(
            persisted_runtime.get("docker_image")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_OM_DOCKER_IMAGE")
            or "openmodelica/openmodelica:v1.26.1-minimal"
        ),
        "challenge_planner_backend": str(
            persisted_runtime.get("challenge_planner_backend")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_PLANNER_BACKEND")
            or challenge.get("baseline_provenance", {}).get("planner_backend")
            or "gemini"
        ),
        "main_planner_backend": str(
            persisted_runtime.get("main_planner_backend")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND")
            or "rule"
        ),
        "night_planner_backend": str(
            persisted_runtime.get("night_planner_backend")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND")
            or "gemini"
        ),
        "realism_mode": str(
            persisted_runtime.get("realism_mode")
            or os.environ.get("GATEFORGE_AGENT_L4_REALISM_MODE")
            or "full"
        ),
        "night_enabled": str(
            persisted_runtime.get("night_enabled")
            or os.environ.get("GATEFORGE_AGENT_L4_REALISM_NIGHT_ENABLED")
            or "1"
        ),
        "main_gate_mode": str(
            persisted_runtime.get("main_gate_mode")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAIN_GATE_MODE")
            or "strict"
        ),
        "night_gate_mode": str(
            persisted_runtime.get("night_gate_mode")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_NIGHT_GATE_MODE")
            or "observe"
        ),
        "challenge_llm_model": llm_model,
        "max_rounds": str(persisted_runtime.get("max_rounds") or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS") or "2"),
        "max_time_sec": str(persisted_runtime.get("max_time_sec") or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC") or "180"),
        "runtime_threshold": str(
            persisted_runtime.get("runtime_threshold")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_RUNTIME_THRESHOLD")
            or "0.2"
        ),
        "live_timeout_sec": str(
            persisted_runtime.get("live_timeout_sec")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC")
            or "90"
        ),
        "live_max_output_chars": str(
            persisted_runtime.get("live_max_output_chars")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_MAX_OUTPUT_CHARS")
            or "2400"
        ),
        "l4_max_rounds": str(
            persisted_runtime.get("l4_max_rounds")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS")
            or "3"
        ),
        "l4_policy_backend": str(
            persisted_runtime.get("l4_policy_backend")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L4_POLICY_BACKEND")
            or "rule"
        ),
        "l4_llm_fallback_threshold": str(
            persisted_runtime.get("l4_llm_fallback_threshold")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L4_LLM_FALLBACK_THRESHOLD")
            or "2"
        ),
        "l4_max_actions_per_round": str(
            persisted_runtime.get("l4_max_actions_per_round")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ACTIONS_PER_ROUND")
            or "3"
        ),
        "min_delta_success_pp": str(min_delta_success_pp),
        "absolute_success_target_pct": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_ABSOLUTE_SUCCESS_TARGET_PCT") or "85"),
        "non_regression_tolerance_pp": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_NON_REGRESSION_TOLERANCE_PP") or "0"),
        "max_regression_worsen_pp": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAX_REGRESSION_WORSEN_PP") or "2"),
        "max_physics_worsen_pp": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAX_PHYSICS_WORSEN_PP") or "2"),
        "l5_infra_must_equal": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L5_INFRA_MUST_EQUAL") or "0"),
        "l5_min_l3_parse_pct": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L5_MIN_L3_PARSE_PCT") or "95"),
        "l5_min_l3_type_pct": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L5_MIN_L3_TYPE_PCT") or "70"),
        "l5_min_l3_stage_pct": str(os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L5_MIN_L3_STAGE_PCT") or "70"),
        "l5_ledger_path": str(
            persisted_runtime.get("l5_ledger_path")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_L5_LEDGER_PATH")
            or (run_root / "private" / "l5_eval_ledger_v1.jsonl")
        ),
        "live_ledger_path": str(
            persisted_runtime.get("live_ledger_path")
            or os.environ.get("GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH")
            or (run_root / "private" / "live_request_ledger.json")
        ),
        "main_profile": str(main_sweep.get("recommended_profile") or "score_v1"),
        "acceptance_mode": acceptance_mode,
        "baseline_reference_success_pct": str(challenge.get("baseline_off_success_at_k_pct") or ""),
        "pack_id": str(manifest.get("pack_id") or challenge.get("pack_id") or ""),
        "pack_version": str(manifest.get("pack_version") or challenge.get("pack_version") or ""),
        "pack_track": str(manifest.get("pack_track") or challenge.get("pack_track") or ""),
        "acceptance_scope": str(manifest.get("acceptance_scope") or challenge.get("acceptance_scope") or ""),
        "challenge_executor_cmd": str(
            persisted_runtime.get("challenge_executor_cmd")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD")
            or ""
        ),
        "main_sweep_executor_cmd": str(
            persisted_runtime.get("main_sweep_executor_cmd")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD")
            or ""
        ),
        "night_sweep_executor_cmd": str(
            persisted_runtime.get("night_sweep_executor_cmd")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD")
            or ""
        ),
        "main_l5_l3_executor_cmd": str(
            persisted_runtime.get("main_l5_l3_executor_cmd")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD")
            or ""
        ),
        "main_l5_l4_executor_cmd": str(
            persisted_runtime.get("main_l5_l4_executor_cmd")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD")
            or ""
        ),
        "night_l5_l3_executor_cmd": str(
            persisted_runtime.get("night_l5_l3_executor_cmd")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD")
            or ""
        ),
        "night_l5_l4_executor_cmd": str(
            persisted_runtime.get("night_l5_l4_executor_cmd")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD")
            or os.environ.get("GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD")
            or ""
        ),
    }


def _run_shell_script(script_name: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **{k: str(v) for k, v in env_overrides.items() if v is not None}}
    return subprocess.run(
        ["bash", str(_repo_root() / "scripts" / script_name)],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _refresh_decision_and_bundle(run_root: Path, cfg: dict, exit_codes: dict[str, int]) -> dict:
    repo_root = _repo_root()
    min_delta_success_pp = str(cfg.get("min_delta_success_pp") or "5")
    absolute_success_target_pct = str(cfg.get("absolute_success_target_pct") or "85")
    non_regression_tolerance_pp = str(cfg.get("non_regression_tolerance_pp") or "0")
    max_regression_worsen_pp = str(cfg.get("max_regression_worsen_pp") or "2")
    max_physics_worsen_pp = str(cfg.get("max_physics_worsen_pp") or "2")
    main_profile = str(cfg.get("main_profile") or "score_v1")
    realism_mode = str(cfg.get("realism_mode") or "")
    challenge_summary = run_root / "challenge" / "frozen_summary.json"
    main_sweep_summary = run_root / "main_sweep" / "summary.json"
    night_sweep_summary = run_root / "night_sweep" / "summary.json"
    main_l5_summary = run_root / "main_l5" / "l5_eval_summary.json"
    main_weekly_summary = run_root / "main_l5" / "l5_weekly_metrics.json"
    night_l5_summary = run_root / "night_l5" / "l5_eval_summary.json"
    night_weekly_summary = run_root / "night_l5" / "l5_weekly_metrics.json"
    decision_json = run_root / "decision_summary.json"
    decision_md = run_root / "decision_summary.md"

    decision_proc = subprocess.run(
        [
            "python3",
            "-m",
            "gateforge.agent_modelica_l4_uplift_decision_v0",
            "--challenge-summary",
            str(challenge_summary),
            "--main-sweep-summary",
            str(main_sweep_summary),
            "--main-l5-summary",
            str(main_l5_summary),
            "--main-weekly-summary",
            str(main_weekly_summary),
            "--night-sweep-summary",
            str(night_sweep_summary),
            "--night-l5-summary",
            str(night_l5_summary),
            "--night-weekly-summary",
            str(night_weekly_summary),
            "--min-delta-success-pp",
            min_delta_success_pp,
            "--absolute-success-target-pct",
            absolute_success_target_pct,
            "--non-regression-tolerance-pp",
            non_regression_tolerance_pp,
            "--max-regression-worsen-pp",
            max_regression_worsen_pp,
            "--max-physics-worsen-pp",
            max_physics_worsen_pp,
            "--night-enabled",
            "1" if _night_enabled(cfg) else "0",
            "--out",
            str(decision_json),
            "--report-out",
            str(decision_md),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ,
    )

    bundle_proc = subprocess.run(
        [
            "python3",
            "-",
            str(run_root),
            str(challenge_summary),
            str(decision_json),
            str(main_sweep_summary),
            str(night_sweep_summary),
            str(main_l5_summary),
            str(main_weekly_summary),
            str(night_l5_summary),
            str(night_weekly_summary),
            str(exit_codes.get("challenge", 0)),
            str(exit_codes.get("main_sweep", 0)),
            str(exit_codes.get("night_sweep", 0)),
            str(exit_codes.get("main_l5", 0)),
            str(exit_codes.get("night_l5", 0)),
            main_profile,
            realism_mode,
            "1" if _night_enabled(cfg) else "0",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ,
        input="""import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
challenge_summary_path = Path(sys.argv[2])
decision_path = Path(sys.argv[3])
main_sweep_path = Path(sys.argv[4])
night_sweep_path = Path(sys.argv[5])
main_l5_path = Path(sys.argv[6])
main_weekly_path = Path(sys.argv[7])
night_l5_path = Path(sys.argv[8])
night_weekly_path = Path(sys.argv[9])
challenge_rc = int(sys.argv[10])
main_sweep_rc = int(sys.argv[11])
night_sweep_rc = int(sys.argv[12])
main_l5_rc = int(sys.argv[13])
night_l5_rc = int(sys.argv[14])
main_profile = str(sys.argv[15] or "").strip()
realism_mode = str(sys.argv[16] or "").strip()
night_enabled = str(sys.argv[17] or "") == "1"

def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

challenge = _load(challenge_summary_path)
decision = _load(decision_path)
main_sweep = _load(main_sweep_path)
night_sweep = _load(night_sweep_path)
main_l5 = _load(main_l5_path)
main_weekly = _load(main_weekly_path)
night_l5 = _load(night_l5_path)
night_weekly = _load(night_weekly_path)

missing = []
for label, payload in (('challenge_summary', challenge), ('decision_summary', decision)):
    if not payload:
        missing.append(label)

challenge_reasons = {
    str(x)
    for x in (challenge.get('reasons') if isinstance(challenge.get('reasons'), list) else [])
    if str(x)
}
baseline_meets_minimum = challenge.get('baseline_meets_minimum') is True
baseline_has_headroom = challenge.get('baseline_has_headroom') is True
baseline_eligible_for_uplift = challenge.get('baseline_eligible_for_uplift')
if baseline_eligible_for_uplift is None:
    baseline_eligible_for_uplift = baseline_meets_minimum and baseline_has_headroom
baseline_execution_valid = challenge.get('baseline_execution_valid')
if baseline_execution_valid is None:
    baseline_execution_valid = 'baseline_off_run_results_empty' not in challenge_reasons
baseline_execution_valid = baseline_execution_valid is True
continued_after_weak_baseline = (
    not baseline_meets_minimum
    and baseline_execution_valid
    and any(
        isinstance(payload, dict) and bool(payload)
        for payload in (main_sweep, main_l5, night_sweep, night_l5)
    )
)
acceptance_mode = str(decision.get('acceptance_mode') or ('absolute_non_regression' if baseline_meets_minimum and not baseline_has_headroom else 'delta_uplift'))
if baseline_meets_minimum or continued_after_weak_baseline:
    required_payloads = [
        ('main_sweep_summary', main_sweep),
        ('main_l5_eval_summary', main_l5),
        ('main_weekly_summary', main_weekly),
    ]
    if night_enabled:
        required_payloads.extend(
            [
                ('night_sweep_summary', night_sweep),
                ('night_l5_eval_summary', night_l5),
                ('night_weekly_summary', night_weekly),
            ]
        )
    for label, payload in required_payloads:
        if not payload:
            missing.append(label)

status = 'PASS' if not missing else 'FAIL'
reasons = []
if challenge_rc != 0 and not challenge:
    reasons.append('challenge_script_nonzero_exit')
if main_sweep_rc != 0 and not main_sweep:
    reasons.append('main_sweep_script_nonzero_exit')
if night_sweep_rc != 0 and not night_sweep:
    reasons.append('night_sweep_script_nonzero_exit')
if main_l5_rc != 0 and not main_l5:
    reasons.append('main_l5_script_nonzero_exit')
if night_l5_rc != 0 and not night_l5:
    reasons.append('night_l5_script_nonzero_exit')
if missing:
    reasons.extend([f'missing_{x}' for x in sorted(set(missing))])
if not night_enabled:
    reasons = [
        x
        for x in reasons
        if x not in {
            'missing_night_sweep_summary',
            'missing_night_l5_eval_summary',
            'missing_night_weekly_summary',
            'night_sweep_script_nonzero_exit',
            'night_l5_script_nonzero_exit',
        }
    ]
    missing = [
        x
        for x in missing
        if x not in {
            'night_sweep_summary',
            'night_l5_eval_summary',
            'night_weekly_summary',
        }
    ]
    status = 'PASS' if not missing else 'FAIL'

bundle = {
    'schema_version': 'agent_modelica_l4_uplift_evidence_bundle_v0',
    'generated_at_utc': datetime.now(timezone.utc).isoformat(),
    'status': status,
    'pack_id': str(challenge.get('pack_id') or ''),
    'pack_version': str(challenge.get('pack_version') or ''),
    'pack_track': str(challenge.get('pack_track') or ''),
    'acceptance_scope': str(challenge.get('acceptance_scope') or ''),
    'decision': str(decision.get('decision') or ''),
    'primary_reason': str(decision.get('primary_reason') or 'none'),
    'acceptance_mode': acceptance_mode,
    'baseline_meets_minimum': baseline_meets_minimum,
    'baseline_has_headroom': baseline_has_headroom,
    'baseline_execution_valid': baseline_execution_valid,
    'continued_after_weak_baseline': continued_after_weak_baseline,
    'baseline_headroom_max_pct': challenge.get('baseline_target_range_pct', {}).get('max') if isinstance(challenge.get('baseline_target_range_pct'), dict) else None,
    'baseline_eligible_for_uplift': baseline_eligible_for_uplift,
    'baseline_in_target_range': challenge.get('baseline_in_target_range'),
    'realism_mode': realism_mode or 'full',
    'night_enabled': night_enabled,
    'main_recommended_profile': main_profile or str(main_sweep.get('recommended_profile') or ''),
    'main_success_at_k_pct': decision.get('main_success_at_k_pct'),
    'absolute_success_target_pct': decision.get('absolute_success_target_pct'),
    'main_delta_success_at_k_pp': decision.get('main_delta_success_at_k_pp'),
    'non_regression_ok': decision.get('non_regression_ok'),
    'main_delta_regression_fail_rate_pp': decision.get('main_delta_regression_fail_rate_pp'),
    'main_delta_physics_fail_rate_pp': decision.get('main_delta_physics_fail_rate_pp'),
    'infra_failure_count_total': decision.get('infra_failure_count_total'),
    'counts_by_failure_type': challenge.get('counts_by_failure_type') if isinstance(challenge.get('counts_by_failure_type'), dict) else {},
    'counts_by_category': challenge.get('counts_by_category') if isinstance(challenge.get('counts_by_category'), dict) else {},
    'main_gate_result': decision.get('main_gate_result'),
    'main_weekly_recommendation': decision.get('main_weekly_recommendation'),
    'main_weekly_recommendation_reason': decision.get('main_weekly_recommendation_reason'),
    'consistency_ok': decision.get('consistency_ok'),
    'script_exit_codes': {
        'challenge': challenge_rc,
        'main_sweep': main_sweep_rc,
        'night_sweep': night_sweep_rc,
        'main_l5_eval': main_l5_rc,
        'night_l5_eval': night_l5_rc,
    },
    'reasons': sorted(
        set(
            [str(x) for x in reasons if str(x)]
            + [str(x) for x in (decision.get('reasons') if isinstance(decision.get('reasons'), list) else []) if str(x)]
        )
    ),
    'paths': {
        'challenge_summary': str(challenge_summary_path),
        'main_sweep_summary': str(main_sweep_path),
        'night_sweep_summary': str(night_sweep_path),
        'main_l5_eval_summary': str(main_l5_path),
        'main_weekly_summary': str(main_weekly_path),
        'night_l5_eval_summary': str(night_l5_path),
        'night_weekly_summary': str(night_weekly_path),
        'decision_summary': str(decision_path),
    },
}

summary_json = out_dir / 'summary.json'
summary_md = out_dir / 'summary.md'
summary_json.write_text(json.dumps(bundle, indent=2), encoding='utf-8')
summary_md.write_text(
    '\\n'.join([
        '# Agent Modelica L4 Uplift Evidence v0',
        '',
        f\"- status: `{bundle.get('status')}`\",
        f\"- decision: `{bundle.get('decision')}`\",
        f\"- primary_reason: `{bundle.get('primary_reason')}`\",
        f\"- acceptance_mode: `{bundle.get('acceptance_mode')}`\",
        f\"- baseline_meets_minimum: `{bundle.get('baseline_meets_minimum')}`\",
        f\"- baseline_has_headroom: `{bundle.get('baseline_has_headroom')}`\",
        f\"- baseline_eligible_for_uplift: `{bundle.get('baseline_eligible_for_uplift')}`\",
        f\"- baseline_in_target_range: `{bundle.get('baseline_in_target_range')}`\",
        f\"- main_recommended_profile: `{bundle.get('main_recommended_profile')}`\",
        f\"- main_success_at_k_pct: `{bundle.get('main_success_at_k_pct')}`\",
        f\"- absolute_success_target_pct: `{bundle.get('absolute_success_target_pct')}`\",
        f\"- main_delta_success_at_k_pp: `{bundle.get('main_delta_success_at_k_pp')}`\",
        f\"- non_regression_ok: `{bundle.get('non_regression_ok')}`\",
        f\"- infra_failure_count_total: `{bundle.get('infra_failure_count_total')}`\",
        f\"- reasons: `{bundle.get('reasons')}`\",
        '',
    ]) + '\\n',
    encoding='utf-8',
)
print(json.dumps(bundle))
if bundle.get('status') != 'PASS':
    raise SystemExit(1)
""",
    )
    return {
        "decision_rc": decision_proc.returncode,
        "bundle_rc": bundle_proc.returncode,
    }


def _resume_stage_details(run_root: Path, stage: str) -> dict:
    current = _load_json(_stage_status_path(run_root, stage))
    current_details = current.get("details") if isinstance(current.get("details"), dict) else {}
    attempts = int(current_details.get("resume_attempts") or 0) + 1
    return {
        "resume_attempts": attempts,
        "resumed_from_status": str(current.get("status") or ""),
        "last_resume_started_at_utc": _utc_now(),
    }


def _write_stage_placeholder(run_root: Path, stage: str, summary_path: Path, reason: str) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if stage in {"main_sweep", "night_sweep"}:
        _write_json(summary_path, {})
    elif stage in {"main_l5", "night_l5"}:
        _write_json(summary_path, {})
        weekly_path = summary_path.parent / "l5_weekly_metrics.json"
        _write_json(weekly_path, {})
    else:
        _write_json(summary_path, {})
    stage_update(
        run_root=str(run_root),
        stage=stage,
        status="SKIPPED",
        exit_code=0,
        summary_path=str(summary_path),
        details={"reason": reason},
    )


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _reset_live_ledger_for_resume(run_root: Path, stage: str, *, restart_budget_window: bool = False) -> None:
    ledger_path = run_root / "private" / "live_request_ledger.json"
    payload = _load_json(ledger_path)
    if not payload:
        return
    disable_live_budget = str(os.getenv("GATEFORGE_AGENT_L4_REALISM_DISABLE_LIVE_BUDGET") or "").strip() == "1"
    try:
        max_requests = 0 if disable_live_budget else max(
            0, int(str(os.getenv("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN") or "").strip() or 80)
        )
    except Exception:
        max_requests = 0 if disable_live_budget else 80
    try:
        max_consecutive_429 = max(1, int(str(os.getenv("GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429") or "").strip() or 3))
    except Exception:
        max_consecutive_429 = 3
    try:
        base_backoff_sec = max(0.0, float(str(os.getenv("GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC") or "").strip() or 5.0))
    except Exception:
        base_backoff_sec = 5.0
    try:
        max_backoff_sec = max(0.0, float(str(os.getenv("GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC") or "").strip() or 60.0))
    except Exception:
        max_backoff_sec = 60.0

    request_count = int(payload.get("request_count") or 0)
    stop_reason = str(payload.get("last_stop_reason") or "").strip()
    should_clear_stop = False
    if stop_reason == "live_request_budget_exceeded" and (max_requests <= 0 or request_count < max_requests):
        should_clear_stop = True
    if stop_reason == "rate_limited":
        should_clear_stop = True
    if restart_budget_window:
        should_clear_stop = True

    payload["live_budget"] = {
        "max_requests_per_run": max_requests,
        "max_consecutive_429": max_consecutive_429,
        "base_backoff_sec": base_backoff_sec,
        "max_backoff_sec": max_backoff_sec,
    }
    payload["last_stage"] = stage
    payload["consecutive_429_count"] = 0
    payload["last_backoff_sec"] = 0.0
    if restart_budget_window:
        payload["request_count"] = 0
        payload["rate_limit_429_count"] = 0
        payload["backoff_count"] = 0
    if should_clear_stop:
        payload["budget_stop_triggered"] = False
        payload["last_stop_reason"] = ""
    _write_json(ledger_path, payload)


def _stage_cleanup_paths(run_root: Path, stage: str) -> list[Path]:
    paths: list[Path] = []
    if stage == "preflight":
        paths.extend([run_root / "environment_preflight_summary.json", run_root / "environment_preflight_summary.md"])
    elif stage == "challenge":
        paths.append(run_root / "challenge")
    elif stage in {"main_sweep", "night_sweep", "main_l5", "night_l5"}:
        paths.append(run_root / stage)
    elif stage == "realism_summary":
        paths.extend(
            [
                run_root / "realism_internal_summary.json",
                run_root / "realism_internal_summary.md",
                run_root / "repair_queue_summary.json",
                run_root / "repair_queue_summary.md",
                run_root / "repair_queue_tasks.json",
                run_root / "wave1_patch_plan_summary.json",
                run_root / "wave1_patch_plan_summary.md",
                run_root / "wave1_patch_plan_tasks.json",
                run_root / "wave1_focused_playbook.json",
            ]
        )
    elif stage == "finalize":
        paths.extend([run_root / "final_run_summary.json", run_root / "final_run_summary.md"])

    if stage in {"challenge", "main_sweep", "night_sweep", "main_l5", "night_l5", "realism_summary"}:
        paths.extend(
            [
                run_root / "summary.json",
                run_root / "summary.md",
                run_root / "decision_summary.json",
                run_root / "decision_summary.md",
            ]
        )
    if stage in {"main_l5", "night_l5", "realism_summary", "finalize"}:
        paths.extend([run_root / "final_run_summary.json", run_root / "final_run_summary.md"])
    return paths


def _invalidate_from_stage(run_root: Path, stage: str) -> None:
    start_idx = STAGE_ORDER.index(stage)
    for downstream_stage in STAGE_ORDER[start_idx:]:
        for path in _stage_cleanup_paths(run_root, downstream_stage):
            _remove_path(path)
        _remove_path(_stage_status_path(run_root, downstream_stage))
        _remove_path(_stage_status_md_path(run_root, downstream_stage))

    run_status = _read_run_status(run_root)
    stages = run_status.get("stages") if isinstance(run_status.get("stages"), dict) else {}
    for downstream_stage in STAGE_ORDER[start_idx:]:
        stages.pop(downstream_stage, None)
    run_status["stages"] = stages
    run_status["updated_at_utc"] = _utc_now()
    run_status["status"] = "RUNNING"
    run_status["current_stage"] = stage
    run_status["finalized"] = False
    run_status["latest_updated"] = False
    _write_json(_run_status_path(run_root), run_status)
    _write_run_status_md(run_root, run_status)


def _run_resumable_stage(run_root: Path, stage: str, cfg: dict, *, restart_live_budget_window: bool = False) -> int:
    summary_path = _scoped_stage_summary_path(run_root, stage)
    details = _resume_stage_details(run_root, stage)
    if stage in {"challenge", "main_sweep", "night_sweep", "main_l5", "night_l5"}:
        _reset_live_ledger_for_resume(run_root, stage, restart_budget_window=restart_live_budget_window)
    _set_run_resuming(run_root, stage)
    stage_update(
        run_root=str(run_root),
        stage=stage,
        status="RUNNING",
        exit_code=0,
        summary_path=str(summary_path),
        details=details,
    )

    if stage == "challenge":
        proc = _run_shell_script(
            "run_agent_modelica_l4_challenge_pack_v0.sh",
            {
                "GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR": str(run_root / "challenge"),
                "GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET": cfg["taskset"],
                "GATEFORGE_AGENT_L4_CHALLENGE_SCALES": cfg["scales"],
                "GATEFORGE_AGENT_L4_CHALLENGE_PACK_ID": cfg["pack_id"],
                "GATEFORGE_AGENT_L4_CHALLENGE_PACK_VERSION": cfg["pack_version"],
                "GATEFORGE_AGENT_L4_CHALLENGE_PACK_TRACK": cfg["pack_track"],
                "GATEFORGE_AGENT_L4_CHALLENGE_ACCEPTANCE_SCOPE": cfg["acceptance_scope"],
                "GATEFORGE_AGENT_L4_CHALLENGE_PLANNER_BACKEND": cfg["challenge_planner_backend"],
                "GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND": cfg["challenge_planner_backend"],
                "GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL": cfg["challenge_llm_model"],
                "GATEFORGE_AGENT_L4_CHALLENGE_BACKEND": cfg["backend"],
                "GATEFORGE_AGENT_L4_CHALLENGE_OM_DOCKER_IMAGE": cfg["docker_image"],
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS": cfg["max_rounds"],
                "GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC": cfg["max_time_sec"],
                "GATEFORGE_AGENT_L4_CHALLENGE_RUNTIME_THRESHOLD": cfg["runtime_threshold"],
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC": cfg["live_timeout_sec"],
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_MAX_OUTPUT_CHARS": cfg["live_max_output_chars"],
                "GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD": cfg["challenge_executor_cmd"],
            },
        )
    elif stage in {"main_sweep", "night_sweep"}:
        planner_backend = cfg["main_planner_backend"] if stage == "main_sweep" else cfg["night_planner_backend"]
        executor_cmd = cfg["main_sweep_executor_cmd"] if stage == "main_sweep" else cfg["night_sweep_executor_cmd"]
        out_dir = run_root / stage
        proc = _run_shell_script(
            "run_agent_modelica_l4_profile_sweep_v0.sh",
            {
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_TASKSET": str(run_root / "challenge" / "taskset_frozen.json"),
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_SCALES": cfg["scales"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_PROFILES": cfg["profiles"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_PLANNER_BACKEND": planner_backend,
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_BACKEND": cfg["backend"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_OM_DOCKER_IMAGE": cfg["docker_image"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_ROUNDS": cfg["max_rounds"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_TIME_SEC": cfg["max_time_sec"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_RUNTIME_THRESHOLD": cfg["runtime_threshold"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_TIMEOUT_SEC": cfg["live_timeout_sec"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_MAX_OUTPUT_CHARS": cfg["live_max_output_chars"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_EXECUTOR_CMD": executor_cmd,
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ROUNDS": cfg["l4_max_rounds"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_POLICY_BACKEND": cfg["l4_policy_backend"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_LLM_FALLBACK_THRESHOLD": cfg["l4_llm_fallback_threshold"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ACTIONS_PER_ROUND": cfg["l4_max_actions_per_round"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MIN_SUCCESS_DELTA_PP": cfg["min_delta_success_pp"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_REGRESSION_WORSEN_PP": cfg["max_regression_worsen_pp"],
                "GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_PHYSICS_WORSEN_PP": cfg["max_physics_worsen_pp"],
            },
        )
        if stage == "main_sweep" and _load_json(summary_path):
            cfg["main_profile"] = str(_load_json(summary_path).get("recommended_profile") or cfg["main_profile"])
    elif stage in {"main_l5", "night_l5"}:
        planner_backend = cfg["main_planner_backend"] if stage == "main_l5" else cfg["night_planner_backend"]
        gate_mode = cfg["main_gate_mode"] if stage == "main_l5" else cfg["night_gate_mode"]
        l3_cmd = cfg["main_l5_l3_executor_cmd"] if stage == "main_l5" else cfg["night_l5_l3_executor_cmd"]
        l4_cmd = cfg["main_l5_l4_executor_cmd"] if stage == "main_l5" else cfg["night_l5_l4_executor_cmd"]
        out_dir = run_root / stage
        proc = _run_shell_script(
            "run_agent_modelica_l5_eval_v1.sh",
            {
                "GATEFORGE_AGENT_L5_EVAL_TASKSET": str(run_root / "challenge" / "taskset_frozen.json"),
                "GATEFORGE_AGENT_L5_EVAL_SCALES": cfg["scales"],
                "GATEFORGE_AGENT_L5_EVAL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_L5_LEDGER_PATH": cfg["l5_ledger_path"],
                "GATEFORGE_AGENT_L5_GATE_MODE": gate_mode,
                "GATEFORGE_AGENT_L5_EVAL_PLANNER_BACKEND": planner_backend,
                "GATEFORGE_AGENT_L5_EVAL_BACKEND": cfg["backend"],
                "GATEFORGE_AGENT_L5_EVAL_OM_DOCKER_IMAGE": cfg["docker_image"],
                "GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS": cfg["max_rounds"],
                "GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC": cfg["max_time_sec"],
                "GATEFORGE_AGENT_L5_EVAL_RUNTIME_THRESHOLD": cfg["runtime_threshold"],
                "GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC": cfg["live_timeout_sec"],
                "GATEFORGE_AGENT_L5_EVAL_LIVE_MAX_OUTPUT_CHARS": cfg["live_max_output_chars"],
                "GATEFORGE_AGENT_L5_ACCEPTANCE_MODE": cfg["acceptance_mode"],
                "GATEFORGE_AGENT_L5_ABSOLUTE_SUCCESS_TARGET_PCT": cfg["absolute_success_target_pct"],
                "GATEFORGE_AGENT_L5_NON_REGRESSION_TOLERANCE_PP": cfg["non_regression_tolerance_pp"],
                "GATEFORGE_AGENT_L5_BASELINE_REFERENCE_SUCCESS_PCT": cfg["baseline_reference_success_pct"],
                "GATEFORGE_AGENT_L4_POLICY_PROFILE": cfg["main_profile"],
                "GATEFORGE_AGENT_L4_POLICY_BACKEND": cfg["l4_policy_backend"],
                "GATEFORGE_AGENT_L4_LLM_FALLBACK_THRESHOLD": cfg["l4_llm_fallback_threshold"],
                "GATEFORGE_AGENT_L4_MAX_ROUNDS": cfg["l4_max_rounds"],
                "GATEFORGE_AGENT_L4_MAX_ACTIONS_PER_ROUND": cfg["l4_max_actions_per_round"],
                "GATEFORGE_AGENT_L5_MIN_DELTA_SUCCESS_PP": cfg["min_delta_success_pp"],
                "GATEFORGE_AGENT_L5_MAX_REGRESSION_WORSEN_PP": cfg["max_regression_worsen_pp"],
                "GATEFORGE_AGENT_L5_MAX_PHYSICS_WORSEN_PP": cfg["max_physics_worsen_pp"],
                "GATEFORGE_AGENT_L5_INFRA_FAILURE_MUST_EQUAL": cfg["l5_infra_must_equal"],
                "GATEFORGE_AGENT_L5_MIN_L3_PARSE_PCT": cfg["l5_min_l3_parse_pct"],
                "GATEFORGE_AGENT_L5_MIN_L3_TYPE_PCT": cfg["l5_min_l3_type_pct"],
                "GATEFORGE_AGENT_L5_MIN_L3_STAGE_PCT": cfg["l5_min_l3_stage_pct"],
                "GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD": l3_cmd,
                "GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD": l4_cmd,
                "GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH": cfg["live_ledger_path"],
                "GATEFORGE_AGENT_LIVE_REQUEST_STAGE": stage,
            },
        )
    elif stage == "realism_summary":
        realism = _maybe_refresh_realism_summary(run_root)
        proc = subprocess.CompletedProcess(args=["realism_summary"], returncode=0 if realism else 1, stdout="", stderr="")
    else:
        proc = subprocess.CompletedProcess(args=[stage], returncode=1, stdout="", stderr="")

    summary_payload = _load_json(summary_path)
    final_status = "PASS" if _stage_payload_complete(stage, summary_path, summary_payload) and proc.returncode == 0 else ("FAIL" if proc.returncode != 0 else "MISSING")
    details.update({"last_resume_exit_code": proc.returncode})
    stage_update(
        run_root=str(run_root),
        stage=stage,
        status=final_status,
        exit_code=proc.returncode,
        summary_path=str(summary_path),
        details=details,
    )
    return int(proc.returncode)


def resume_run(
    *,
    out_dir: str,
    run_root: str = "",
    run_id: str = "",
    stages: str = "auto",
    update_latest: bool = True,
    force_rerun_completed: bool = False,
) -> dict:
    _bootstrap_runtime_env()
    if run_root:
        root = Path(run_root)
    elif run_id:
        root = Path(out_dir) / "runs" / run_id
    else:
        latest = _load_json(Path(out_dir) / "latest_run.json")
        latest_root = str(latest.get("run_root") or "")
        root = Path(latest_root) if latest_root else (Path(out_dir) / "runs" / run_id)
    if not root.exists():
        return {"schema_version": SCHEMA_VERSION, "status": "NOT_FOUND", "reason": "run_root_missing"}
    if not _load_json(_run_manifest_path(root)) and not _load_json(_run_status_path(root)):
        return {"schema_version": SCHEMA_VERSION, "status": "NOT_FOUND", "reason": "run_root_not_scoped"}

    states = _infer_scoped_stage_states(root)
    cfg = _runtime_config(root)
    if not _night_enabled(cfg):
        for skipped_stage in ("night_sweep", "night_l5"):
            row = states.get(skipped_stage) or {}
            if not bool(row.get("complete")) and str(row.get("status") or "").upper() != "SKIPPED":
                _write_stage_placeholder(root, skipped_stage, _scoped_stage_summary_path(root, skipped_stage), "lean_mode_night_disabled")
        states = _infer_scoped_stage_states(root)

    stage_list = []
    if str(stages or "auto").strip().lower() == "auto":
        stage_list = _auto_resume_stages(states, cfg)
    else:
        requested = [str(x).strip() for x in str(stages).split(",") if str(x).strip()]
        for stage in requested:
            if stage not in RESUMABLE_STAGE_ORDER:
                continue
            if not _night_enabled(cfg) and stage in {"night_sweep", "night_l5"}:
                _write_stage_placeholder(root, stage, _scoped_stage_summary_path(root, stage), "lean_mode_night_disabled")
                continue
            if force_rerun_completed or not bool((states.get(stage) or {}).get("complete")):
                stage_list.append(stage)

    if not stage_list:
        finalized = finalize_run(out_dir=out_dir, run_root=str(root), update_latest=update_latest)
        return report_run(out_dir=out_dir, run_root=str(root))

    invalidated = False
    for stage in stage_list:
        if force_rerun_completed and bool((states.get(stage) or {}).get("complete")):
            _invalidate_from_stage(root, stage)
            invalidated = True
            break
    if invalidated:
        states = _infer_scoped_stage_states(root)
        if not _night_enabled(cfg):
            for skipped_stage in ("night_sweep", "night_l5"):
                row = states.get(skipped_stage) or {}
                if not bool(row.get("complete")) and str(row.get("status") or "").upper() != "SKIPPED":
                    _write_stage_placeholder(root, skipped_stage, _scoped_stage_summary_path(root, skipped_stage), "lean_mode_night_disabled")
            states = _infer_scoped_stage_states(root)

    exit_codes = {
        "challenge": 0,
        "main_sweep": 0,
        "night_sweep": 0,
        "main_l5": 0,
        "night_l5": 0,
    }
    for stage in stage_list:
        rc = _run_resumable_stage(root, stage, cfg, restart_live_budget_window=force_rerun_completed)
        if stage in exit_codes:
            exit_codes[stage] = rc

    bundle_meta = _refresh_decision_and_bundle(root, cfg, exit_codes)
    if bundle_meta.get("decision_rc") != 0 or bundle_meta.get("bundle_rc") != 0:
        stage_update(
            run_root=str(root),
            stage="realism_summary",
            status=str((_load_json(_stage_status_path(root, "realism_summary")).get("status") or "MISSING")),
            exit_code=_safe_int(bundle_meta.get("bundle_rc")),
            summary_path=str(root / "realism_internal_summary.json"),
            details={"bundle_refresh_failed": True},
        )

    finalized = finalize_run(out_dir=out_dir, run_root=str(root), update_latest=update_latest)
    return report_run(out_dir=out_dir, run_root=str(root))


def _final_status_from_artifacts(run_root: Path) -> tuple[dict, dict]:
    run_status = _read_run_status(run_root)
    manifest = _load_json(_run_manifest_path(run_root))
    evidence = _load_json(run_root / "summary.json")
    challenge = _load_json(run_root / "challenge" / "frozen_summary.json")
    preflight = _load_json(run_root / "environment_preflight_summary.json")
    realism = _load_json(run_root / "realism_internal_summary.json")
    main_l5 = _load_json(run_root / "main_l5" / "l5_eval_summary.json")
    l3_run = _load_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json")

    baseline_pct = _safe_float(challenge.get("baseline_off_success_at_k_pct"))
    challenge_reasons = {str(x) for x in (challenge.get("reasons") if isinstance(challenge.get("reasons"), list) else []) if str(x)}
    baseline_execution_valid = challenge.get("baseline_execution_valid")
    if baseline_execution_valid is None:
        baseline_execution_valid = "baseline_off_run_results_empty" not in challenge_reasons
    baseline_execution_valid = baseline_execution_valid is True
    baseline_has_headroom = challenge.get("baseline_has_headroom")
    baseline_saturated = bool(
        (baseline_pct is not None and baseline_pct >= 100.0)
        or baseline_has_headroom is False
    )
    baseline_state = "unknown"
    if baseline_pct is not None:
        baseline_state = "baseline_saturated" if baseline_saturated else "headroom_available"

    evidence_status = str(evidence.get("status") or "").upper()
    status = "PASS"
    primary_reason = str(evidence.get("primary_reason") or "none")
    decision = ""
    if evidence_status not in {"", "BLOCKED"}:
        decision = str(evidence.get("decision") or "")
    completion_reason = ""

    preflight_blocked = str(preflight.get("status") or "").upper() == "BLOCKED"
    preflight_blockers = {
        str(x)
        for x in (preflight.get("blockers") if isinstance(preflight.get("blockers"), list) else [])
        if str(x)
    }
    continued_after_weak_baseline = bool(evidence.get("continued_after_weak_baseline"))
    live_budget_stop_reason = str(evidence.get("live_budget_stop_reason") or "")

    if preflight_blocked and not challenge:
        status = "BLOCKED"
        primary_reason = "stale_base_taskset" if "stale_base_taskset" in preflight_blockers else "environment_preflight_failed"
        completion_reason = primary_reason
    elif not baseline_execution_valid:
        status = "BLOCKED"
        primary_reason = "baseline_execution_failed"
        completion_reason = primary_reason
    elif not challenge or baseline_pct is None:
        status = "BLOCKED"
        primary_reason = "challenge_incomplete"
        completion_reason = primary_reason
    elif live_budget_stop_reason in {"live_request_budget_exceeded", "rate_limited"}:
        status = "BLOCKED"
        primary_reason = live_budget_stop_reason
        completion_reason = primary_reason
    elif not main_l5 or not (l3_run.get("records") if isinstance(l3_run.get("records"), list) else []):
        status = "NEEDS_REVIEW"
        primary_reason = "baseline_too_weak" if (continued_after_weak_baseline and evidence_status == "PASS") else "downstream_evidence_incomplete"
        completion_reason = primary_reason
    elif realism:
        realism_status = str(realism.get("status") or "").upper()
        if continued_after_weak_baseline and evidence_status == "PASS":
            status = "NEEDS_REVIEW"
            primary_reason = "baseline_too_weak"
            completion_reason = primary_reason
        elif realism_status in {"FAIL", "NEEDS_REVIEW"}:
            status = "NEEDS_REVIEW"
            primary_reason = "taxonomy_alignment_failed"
            completion_reason = primary_reason
    elif evidence:
        status = "PASS"

    mismatch_summary = realism.get("mismatch_summary") if isinstance(realism.get("mismatch_summary"), dict) else {}
    manifestation_view = realism.get("failure_manifestation_view") if isinstance(realism.get("failure_manifestation_view"), dict) else {}
    outcome_view = realism.get("final_outcome_view") if isinstance(realism.get("final_outcome_view"), dict) else {}
    taxonomy_alignment_status = str(realism.get("status") or "INCOMPLETE")
    taxonomy_alignment_recommendation = str(realism.get("recommendation") or "")
    manifestation_alignment_status = str(manifestation_view.get("status") or taxonomy_alignment_status)
    outcome_alignment_status = str(outcome_view.get("status") or "INCOMPLETE")
    if str(realism.get("status") or "").upper() == "BLOCKED":
        taxonomy_alignment_status = "INCOMPLETE"
        taxonomy_alignment_recommendation = ""
        manifestation_alignment_status = "INCOMPLETE"
        outcome_alignment_status = "INCOMPLETE"

    summary = {
        "schema_version": FINAL_RUN_SUMMARY_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "run_id": str(run_status.get("run_id") or manifest.get("run_id") or run_root.name),
        "run_root": str(run_root),
        "status": status,
        "decision": decision,
        "primary_reason": primary_reason,
        "acceptance_mode": str(evidence.get("acceptance_mode") or ""),
        "baseline_state": baseline_state,
        "baseline_off_success_at_k_pct": baseline_pct,
        "continued_after_weak_baseline": continued_after_weak_baseline,
        "realism_mode": str(evidence.get("realism_mode") or ""),
        "night_enabled": evidence.get("night_enabled"),
        "live_budget": evidence.get("live_budget") if isinstance(evidence.get("live_budget"), dict) else {},
        "live_request_count": evidence.get("live_request_count"),
        "rate_limit_429_count": evidence.get("rate_limit_429_count"),
        "budget_stop_triggered": bool(evidence.get("budget_stop_triggered")),
        "main_success_at_k_pct": evidence.get("main_success_at_k_pct"),
        "connector_subtype_match_rate_pct": mismatch_summary.get("connector_subtype_match_rate_pct"),
        "initialization_simulate_stage_rate_pct": mismatch_summary.get("initialization_simulate_stage_rate_pct"),
        "initialization_truncated_by_check_count": mismatch_summary.get("initialization_truncated_by_check_count"),
        "taxonomy_view_mode": str(realism.get("taxonomy_view_mode") or ""),
        "taxonomy_alignment_status": taxonomy_alignment_status,
        "taxonomy_alignment_recommendation": taxonomy_alignment_recommendation,
        "manifestation_alignment_status": manifestation_alignment_status,
        "outcome_alignment_status": outcome_alignment_status,
        "completion_reason": completion_reason,
        "pack_id": str(manifest.get("pack_id") or evidence.get("pack_id") or challenge.get("pack_id") or ""),
        "pack_version": str(manifest.get("pack_version") or evidence.get("pack_version") or challenge.get("pack_version") or ""),
        "pack_track": str(manifest.get("pack_track") or evidence.get("pack_track") or challenge.get("pack_track") or ""),
        "acceptance_scope": str(manifest.get("acceptance_scope") or evidence.get("acceptance_scope") or challenge.get("acceptance_scope") or ""),
        "paths": {
            "evidence_summary": str(run_root / "summary.json"),
            "challenge_summary": str(run_root / "challenge" / "frozen_summary.json"),
            "main_l5_summary": str(run_root / "main_l5" / "l5_eval_summary.json"),
            "realism_internal_summary": str(run_root / "realism_internal_summary.json"),
        },
    }
    return summary, run_status


def finalize_run(
    *,
    out_dir: str,
    run_root: str,
    update_latest: bool,
) -> dict:
    root = Path(run_root)
    out_root = Path(out_dir)
    manifest = _load_json(_run_manifest_path(root))
    runtime_cfg = manifest.get("runtime_config") if isinstance(manifest.get("runtime_config"), dict) else {}
    if runtime_cfg:
        states = _infer_scoped_stage_states(root)
        exit_codes: dict[str, int] = {}
        for stage in ("challenge", "main_sweep", "night_sweep", "main_l5", "night_l5"):
            parsed = _safe_int((states.get(stage) or {}).get("exit_code"))
            exit_codes[stage] = 0 if parsed is None else parsed
        _refresh_decision_and_bundle(root, runtime_cfg, exit_codes)
    _maybe_refresh_realism_summary(root)
    summary, run_status = _final_status_from_artifacts(root)
    _write_json(_final_summary_path(root), summary)
    try:
        from .agent_modelica_realism_repair_queue_v1 import build_repair_queue_v1

        repair_queue = build_repair_queue_v1(run_root=str(root), update_final_summary=True)
    except Exception:
        repair_queue = {}
    try:
        from .agent_modelica_realism_wave1_patch_plan_v1 import build_wave1_patch_plan_v1

        patch_plan = build_wave1_patch_plan_v1(run_root=str(root), update_final_summary=True)
    except Exception:
        patch_plan = {}
    if repair_queue:
        summary["repair_queue_status"] = repair_queue.get("status")
        summary["repair_queue_path"] = str(root / "repair_queue_summary.json")
        summary["top_repair_priority"] = str(repair_queue.get("top_repair_priority") or "")
        paths = summary.get("paths") if isinstance(summary.get("paths"), dict) else {}
        paths["repair_queue_summary"] = str(root / "repair_queue_summary.json")
        paths["repair_queue_tasks"] = str(root / "repair_queue_tasks.json")
        summary["paths"] = paths
    if patch_plan:
        summary["patch_plan_status"] = patch_plan.get("status")
        summary["patch_plan_path"] = str(root / "wave1_patch_plan_summary.json")
        summary["top_patch_target"] = str(patch_plan.get("top_patch_target") or "")
        summary["focused_playbook_path"] = str(patch_plan.get("focused_playbook_path") or "")
        paths = summary.get("paths") if isinstance(summary.get("paths"), dict) else {}
        paths["wave1_patch_plan_summary"] = str(root / "wave1_patch_plan_summary.json")
        paths["wave1_patch_plan_tasks"] = str(root / "wave1_patch_plan_tasks.json")
        if patch_plan.get("focused_playbook_path"):
            paths["wave1_focused_playbook"] = str(root / "wave1_focused_playbook.json")
        summary["paths"] = paths
    if repair_queue or patch_plan:
        _write_json(_final_summary_path(root), summary)
    _write_md(
        _final_summary_md_path(root),
        [
            "# Agent Modelica Realism Final Run Summary",
            "",
            f"- run_id: `{summary.get('run_id')}`",
            f"- status: `{summary.get('status')}`",
            f"- decision: `{summary.get('decision')}`",
            f"- primary_reason: `{summary.get('primary_reason')}`",
            f"- acceptance_mode: `{summary.get('acceptance_mode')}`",
            f"- baseline_state: `{summary.get('baseline_state')}`",
            f"- baseline_off_success_at_k_pct: `{summary.get('baseline_off_success_at_k_pct')}`",
            f"- taxonomy_view_mode: `{summary.get('taxonomy_view_mode')}`",
            f"- taxonomy_alignment_status: `{summary.get('taxonomy_alignment_status')}`",
            f"- taxonomy_alignment_recommendation: `{summary.get('taxonomy_alignment_recommendation')}`",
            f"- manifestation_alignment_status: `{summary.get('manifestation_alignment_status')}`",
            f"- outcome_alignment_status: `{summary.get('outcome_alignment_status')}`",
            f"- repair_queue_status: `{summary.get('repair_queue_status')}`",
            f"- top_repair_priority: `{summary.get('top_repair_priority')}`",
            f"- patch_plan_status: `{summary.get('patch_plan_status')}`",
            f"- top_patch_target: `{summary.get('top_patch_target')}`",
        ],
    )
    stage_update(
        run_root=str(root),
        stage="finalize",
        status="PASS",
        exit_code=0,
        summary_path=str(_final_summary_path(root)),
        details={"final_status": summary.get("status"), "primary_reason": summary.get("primary_reason")},
    )
    run_status = _read_run_status(root)
    run_status["updated_at_utc"] = _utc_now()
    run_status["status"] = str(summary.get("status") or run_status.get("status") or "")
    run_status["current_stage"] = "finalize"
    run_status["finalized"] = True
    run_status["final_run_summary_path"] = str(_final_summary_path(root))
    run_status["latest_updated"] = False

    if update_latest and str(summary.get("status") or "").upper() != "BLOCKED":
        latest_run = {
            "schema_version": LATEST_RUN_SCHEMA_VERSION,
            "generated_at_utc": _utc_now(),
            "run_id": summary.get("run_id"),
            "run_root": str(root),
            "status": summary.get("status"),
            "final_run_summary_path": str(_final_summary_path(root)),
        }
        _write_json(out_root / "latest_run.json", latest_run)
        _write_json(out_root / "latest_summary.json", summary)
        realism = _load_json(root / "realism_internal_summary.json")
        if realism:
            _write_json(out_root / "latest_realism_internal_summary.json", realism)
        run_status["latest_updated"] = True

    _write_json(_run_status_path(root), run_status)
    _write_run_status_md(root, run_status)
    return summary


def _link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        relative = os.path.relpath(src, start=dst.parent)
        dst.symlink_to(relative, target_is_directory=src.is_dir())
    except Exception:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def _update_manifest_for_legacy(run_root: Path, *, out_dir: str) -> None:
    manifest = _load_json(_run_manifest_path(run_root))
    status = _read_run_status(run_root)
    manifest["run_origin"] = "legacy_adoption"
    manifest["legacy_source_out_dir"] = str(Path(out_dir))
    status["run_origin"] = "legacy_adoption"
    status["legacy_source_out_dir"] = str(Path(out_dir))
    _write_json(_run_manifest_path(run_root), manifest)
    _write_json(_run_status_path(run_root), status)
    _write_run_status_md(run_root, status)


def adopt_legacy_run(
    *,
    out_dir: str,
    run_id: str = LEGACY_RUN_ID,
    update_latest: bool = True,
) -> dict:
    out_root = Path(out_dir)
    run_root = out_root / "runs" / run_id
    existing_manifest = _load_json(_run_manifest_path(run_root))
    if existing_manifest.get("legacy_source_out_dir") == str(out_root) and _load_json(_final_summary_path(run_root)):
        return report_run(out_dir=out_dir, run_root=str(run_root))

    summary = _load_json(out_root / "summary.json")
    challenge = _load_json(out_root / "challenge" / "frozen_summary.json")
    init_run(
        out_dir=str(out_root),
        run_root=str(run_root),
        run_id=run_id,
        pack_id=str(summary.get("pack_id") or challenge.get("pack_id") or ""),
        pack_version=str(summary.get("pack_version") or challenge.get("pack_version") or ""),
        pack_track=str(summary.get("pack_track") or challenge.get("pack_track") or "realism"),
        acceptance_scope=str(summary.get("acceptance_scope") or challenge.get("acceptance_scope") or "independent_validation"),
        base_taskset=str(out_root / "challenge" / "taskset_frozen.json"),
        lock_path="",
        update_latest=update_latest,
    )
    _update_manifest_for_legacy(run_root, out_dir=str(out_root))

    paths = _legacy_artifact_paths(out_root)
    for rel in ("summary.json", "decision_summary.json", "decision_summary.md", "environment_preflight_summary.json", "environment_preflight_summary.md"):
        src = out_root / rel
        if src.exists():
            _link_or_copy(src, run_root / rel)
    for name in ("challenge", "main_sweep", "night_sweep", "main_l5", "night_l5"):
        src = out_root / name
        if src.exists():
            _link_or_copy(src, run_root / name)

    states = _legacy_stage_states(out_root)
    active_pid = _discover_legacy_active_pid(out_root)
    current_stage = _current_stage_from_states(states, finalized=False)
    for stage in STAGE_ORDER:
        if stage == "realism_summary":
            continue
        row = states.get(stage) if isinstance(states.get(stage), dict) else {}
        if stage == "finalize":
            continue
        if bool(row.get("complete")):
            stage_status = str(row.get("status") or "PASS")
        else:
            if active_pid and stage == current_stage:
                stage_status = "RUNNING"
            elif not active_pid:
                stage_status = "MISSING"
            else:
                stage_status = ""
        if stage_status:
            stage_update(
                run_root=str(run_root),
                stage=stage,
                status=stage_status,
                exit_code=0,
                summary_path=str(row.get("summary_path") or ""),
            )

    realism = _maybe_refresh_realism_summary(run_root)
    stage_update(
        run_root=str(run_root),
        stage="realism_summary",
        status="PASS" if realism else ("RUNNING" if active_pid else "MISSING"),
        exit_code=0 if realism else None,
        summary_path=str(run_root / "realism_internal_summary.json"),
    )
    final = finalize_run(out_dir=str(out_root), run_root=str(run_root), update_latest=update_latest)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": final.get("status"),
        "run_id": run_id,
        "run_root": str(run_root),
        "adopted_from_legacy": True,
        "final_run_summary_path": str(_final_summary_path(run_root)),
    }


def report_run(*, out_dir: str, run_id: str = "", run_root: str = "") -> dict:
    out_root = Path(out_dir)
    root = Path(run_root) if run_root else None
    run_mode = "scoped"
    active_pid: int | None = None

    if root is None or str(root) in {"", "."}:
        if run_id:
            root = out_root / "runs" / run_id
        else:
            lock = _load_json(out_root / ".active_run_lock.json")
            lock_root = str(lock.get("run_root") or "")
            lock_pid = _safe_int(lock.get("pid"))
            if lock_root and _pid_alive(lock_pid):
                root = Path(lock_root)
                active_pid = lock_pid
            else:
                latest = _load_json(out_root / "latest_run.json")
                latest_root = str(latest.get("run_root") or "")
                if latest_root:
                    root = Path(latest_root)

    if root is not None and root.exists():
        active_pid = active_pid or _active_scoped_pid(root)
        run_status = _read_run_status(root)
        final_summary = _load_json(_final_summary_path(root))
        states = _infer_scoped_stage_states(root)
        completed_stages, missing_stages = _completed_and_missing_stages(states)
        finalized = bool(run_status.get("finalized")) or _nonempty_dict(final_summary)
        cfg = _runtime_config(root)
        next_resume_stages = _auto_resume_stages(states, cfg)
        resume_blockers = _resume_blockers("scoped", active_pid=active_pid, states=states)
        finalize_ready = False
        if not finalized:
            if not active_pid and (completed_stages or missing_stages):
                finalize_ready = True
            if all(str((states.get(stage) or {}).get("status") or "").upper() in TERMINAL_STAGE_STATUSES for stage in STAGE_ORDER[:-1]):
                finalize_ready = True
        current_stage = str(run_status.get("current_stage") or _current_stage_from_states(states, finalized))
        if finalized and not next_resume_stages:
            current_stage = "finalize"
        payload_status = str(run_status.get("status") or "UNKNOWN")
        if finalized and not next_resume_stages:
            payload_status = str(final_summary.get("status") or payload_status)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": _utc_now(),
            "run_mode": run_mode,
            "run_id": str(run_status.get("run_id") or root.name),
            "run_root": str(root),
            "status": payload_status,
            "current_stage": current_stage,
            "active_pid": active_pid,
            "finalized": finalized,
            "latest_updated": bool(run_status.get("latest_updated")),
            "completed_stages": completed_stages,
            "missing_stages": missing_stages,
            "finalize_ready": finalize_ready,
            "final_run_summary_path": str(run_status.get("final_run_summary_path") or _final_summary_path(root)),
            "latest_summary_path": str(out_root / "latest_summary.json"),
            "resume_recommended": (not active_pid) and bool(next_resume_stages),
            "next_resume_stages": next_resume_stages,
            "resume_blockers": resume_blockers,
        }
        if final_summary:
            payload["decision"] = final_summary.get("decision")
            payload["primary_reason"] = final_summary.get("primary_reason")
            payload["taxonomy_view_mode"] = final_summary.get("taxonomy_view_mode")
            payload["taxonomy_alignment_status"] = final_summary.get("taxonomy_alignment_status")
            payload["manifestation_alignment_status"] = final_summary.get("manifestation_alignment_status")
            payload["outcome_alignment_status"] = final_summary.get("outcome_alignment_status")
            payload["repair_queue_status"] = final_summary.get("repair_queue_status")
            payload["top_repair_priority"] = final_summary.get("top_repair_priority")
            payload["patch_plan_status"] = final_summary.get("patch_plan_status")
            payload["top_patch_target"] = final_summary.get("top_patch_target")
        return payload

    if _legacy_artifacts_exist(out_root):
        run_mode = "legacy"
        active_pid = _discover_legacy_active_pid(out_root)
        states = _legacy_stage_states(out_root)
        completed_stages, missing_stages = _completed_and_missing_stages(states)
        current_stage = _current_stage_from_states(states, finalized=False)
        finalize_ready = active_pid is None and bool(completed_stages or missing_stages)
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": _utc_now(),
            "run_mode": run_mode,
            "run_id": "",
            "expected_run_id": LEGACY_RUN_ID,
            "run_root": "",
            "status": "RUNNING" if active_pid else "NEEDS_REVIEW",
            "current_stage": current_stage,
            "active_pid": active_pid,
            "finalized": False,
            "latest_updated": False,
            "completed_stages": completed_stages,
            "missing_stages": missing_stages,
            "finalize_ready": finalize_ready,
            "final_run_summary_path": "",
            "expected_final_run_summary_path": str(out_root / "runs" / LEGACY_RUN_ID / "final_run_summary.json"),
            "latest_summary_path": str(out_root / "latest_summary.json"),
            "resume_recommended": False,
            "next_resume_stages": [],
            "resume_blockers": _resume_blockers("legacy", active_pid=active_pid, states=states),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "NOT_FOUND",
        "reason": "no_run_found",
    }


def watch_run(
    *,
    out_dir: str,
    run_id: str = "",
    run_root: str = "",
    interval_sec: int = 30,
    legacy_adopt: bool = True,
    finalize_on_process_exit: bool = True,
    update_latest: bool = True,
    max_polls: int = 0,
) -> dict:
    polls = 0
    while True:
        status = report_run(out_dir=out_dir, run_id=run_id, run_root=run_root)
        if status.get("status") == "NOT_FOUND":
            return status

        run_mode = str(status.get("run_mode") or "")
        finalized = bool(status.get("finalized"))
        finalize_ready = bool(status.get("finalize_ready"))
        if finalized:
            return status
        if finalize_ready and finalize_on_process_exit:
            if run_mode == "legacy" and legacy_adopt:
                adopted = adopt_legacy_run(out_dir=out_dir, run_id=LEGACY_RUN_ID, update_latest=update_latest)
                return report_run(out_dir=out_dir, run_root=str(adopted.get("run_root") or ""))
            if run_mode == "scoped":
                finalized_summary = finalize_run(
                    out_dir=out_dir,
                    run_root=str(status.get("run_root") or run_root),
                    update_latest=update_latest,
                )
                return report_run(out_dir=out_dir, run_root=str(finalized_summary.get("run_root") or status.get("run_root") or ""))

        polls += 1
        if max_polls > 0 and polls >= max_polls:
            return status
        time.sleep(max(0, interval_sec))


def main() -> None:
    parser = argparse.ArgumentParser(description="Helpers for Agent Modelica realism evidence run lifecycle")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_parser = sub.add_parser("init-run")
    init_parser.add_argument("--out-dir", required=True)
    init_parser.add_argument("--run-root", required=True)
    init_parser.add_argument("--run-id", required=True)
    init_parser.add_argument("--pack-id", required=True)
    init_parser.add_argument("--pack-version", required=True)
    init_parser.add_argument("--pack-track", required=True)
    init_parser.add_argument("--acceptance-scope", required=True)
    init_parser.add_argument("--base-taskset", required=True)
    init_parser.add_argument("--lock-path", required=True)
    init_parser.add_argument("--update-latest", default="1")
    init_parser.add_argument("--runtime-config-json", default="")

    stage_parser = sub.add_parser("stage-update")
    stage_parser.add_argument("--run-root", required=True)
    stage_parser.add_argument("--stage", required=True)
    stage_parser.add_argument("--status", required=True)
    stage_parser.add_argument("--exit-code", default="")
    stage_parser.add_argument("--summary-path", default="")
    stage_parser.add_argument("--details-json", default="")

    finalize_parser = sub.add_parser("finalize-run")
    finalize_parser.add_argument("--out-dir", required=True)
    finalize_parser.add_argument("--run-root", required=True)
    finalize_parser.add_argument("--update-latest", default="1")

    report_parser = sub.add_parser("report")
    report_parser.add_argument("--out-dir", required=True)
    report_parser.add_argument("--run-id", default="")
    report_parser.add_argument("--run-root", default="")

    adopt_parser = sub.add_parser("adopt-legacy")
    adopt_parser.add_argument("--out-dir", required=True)
    adopt_parser.add_argument("--run-id", default=LEGACY_RUN_ID)
    adopt_parser.add_argument("--update-latest", default="1")

    resume_parser = sub.add_parser("resume-run")
    resume_parser.add_argument("--out-dir", required=True)
    resume_parser.add_argument("--run-id", default="")
    resume_parser.add_argument("--run-root", default="")
    resume_parser.add_argument("--stages", default="auto")
    resume_parser.add_argument("--update-latest", default="1")
    resume_parser.add_argument("--force-rerun-completed", default="0")

    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--out-dir", required=True)
    watch_parser.add_argument("--run-id", default="")
    watch_parser.add_argument("--run-root", default="")
    watch_parser.add_argument("--interval-sec", default="30")
    watch_parser.add_argument("--legacy-adopt", default="1")
    watch_parser.add_argument("--finalize-on-process-exit", default="1")
    watch_parser.add_argument("--update-latest", default="1")
    watch_parser.add_argument("--max-polls", default="0")

    args = parser.parse_args()

    if args.cmd == "init-run":
        runtime_config = {}
        if str(args.runtime_config_json or "").strip():
            try:
                loaded = json.loads(args.runtime_config_json)
                if isinstance(loaded, dict):
                    runtime_config = loaded
            except Exception:
                runtime_config = {}
        payload = init_run(
            out_dir=args.out_dir,
            run_root=args.run_root,
            run_id=args.run_id,
            pack_id=args.pack_id,
            pack_version=args.pack_version,
            pack_track=args.pack_track,
            acceptance_scope=args.acceptance_scope,
            base_taskset=args.base_taskset,
            lock_path=args.lock_path,
            update_latest=_bool_env(args.update_latest, default=True),
            runtime_config=runtime_config,
        )
    elif args.cmd == "stage-update":
        details = {}
        if str(args.details_json or "").strip():
            try:
                loaded = json.loads(args.details_json)
                if isinstance(loaded, dict):
                    details = loaded
            except Exception:
                details = {}
        payload = stage_update(
            run_root=args.run_root,
            stage=args.stage,
            status=args.status,
            exit_code=_safe_int(args.exit_code),
            summary_path=args.summary_path,
            details=details,
        )
    elif args.cmd == "finalize-run":
        payload = finalize_run(
            out_dir=args.out_dir,
            run_root=args.run_root,
            update_latest=_bool_env(args.update_latest, default=True),
        )
    elif args.cmd == "adopt-legacy":
        payload = adopt_legacy_run(
            out_dir=args.out_dir,
            run_id=args.run_id,
            update_latest=_bool_env(args.update_latest, default=True),
        )
    elif args.cmd == "resume-run":
        payload = resume_run(
            out_dir=args.out_dir,
            run_root=args.run_root,
            run_id=args.run_id,
            stages=args.stages,
            update_latest=_bool_env(args.update_latest, default=True),
            force_rerun_completed=_bool_env(args.force_rerun_completed, default=False),
        )
    elif args.cmd == "watch":
        payload = watch_run(
            out_dir=args.out_dir,
            run_id=args.run_id,
            run_root=args.run_root,
            interval_sec=_safe_int(args.interval_sec) or 30,
            legacy_adopt=_bool_env(args.legacy_adopt, default=True),
            finalize_on_process_exit=_bool_env(args.finalize_on_process_exit, default=True),
            update_latest=_bool_env(args.update_latest, default=True),
            max_polls=_safe_int(args.max_polls) or 0,
        )
    else:
        payload = report_run(out_dir=args.out_dir, run_id=args.run_id, run_root=args.run_root)

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
