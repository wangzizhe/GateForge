from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_live_executor_v1 import DEFAULT_DOCKER_IMAGE, _apply_source_model_repair
from .agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from .agent_modelica_rule_engine_v1 import RuleContext, build_default_rule_registry
from .agent_modelica_v0_3_13_residual_signal_whitelist import (
    DEFAULT_OUT_DIR as DEFAULT_WHITELIST_OUT_DIR,
    build_residual_signal_whitelist,
    match_residual_signal_cluster,
)


SCHEMA_VERSION = "agent_modelica_v0_3_13_trajectory_preview"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_trajectory_preview"
DEFAULT_INPUT_DIR = "artifacts/agent_modelica_block_a_dual_layer_candidates_v0_3_5"
LATE_STAGE_PREFIXES = ("stage_4_", "stage_5_")
PreviewRunner = Callable[[dict, str], dict]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _load_tasks(input_path: str | Path) -> list[dict]:
    target = Path(input_path)
    rows: list[dict] = []
    if target.is_dir():
        for child in sorted(target.glob("*.json")):
            if child.name.endswith("lane_summary.json") or child.name == "lane_summary.json":
                continue
            payload = _load_json(child)
            if payload:
                rows.append(payload)
        return rows
    payload = _load_json(target)
    task_rows = payload.get("tasks")
    if isinstance(task_rows, list):
        return [row for row in task_rows if isinstance(row, dict)]
    return []


def _extract_model_name(model_text: str, fallback: str) -> str:
    match = re.search(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\b", str(model_text or ""), re.MULTILINE)
    if match:
        return str(match.group(1))
    return str(Path(fallback).stem or "PreviewModel")


def preview_surface_fix(task: dict) -> dict:
    registry = build_default_rule_registry()
    ctx = RuleContext(
        current_text=str(task.get("mutated_model_text") or ""),
        declared_failure_type=str(task.get("declared_failure_type") or task.get("failure_type") or ""),
        source_model_text=str(task.get("source_model_text") or ""),
        current_round=1,
    )
    results = registry.try_repairs(ctx)
    applied = next((row for row in results if row.applied), None)
    if applied is None:
        return {
            "surface_fixable_by_rule": False,
            "surface_rule_id": "",
            "surface_rule_reason": "no_deterministic_surface_rule_applied",
            "post_rule_text": str(task.get("mutated_model_text") or ""),
            "post_rule_source_repair_applied": False,
            "post_rule_source_repair_reason": "",
        }

    post_rule_text = str(applied.new_text or "")
    _, source_repair = _apply_source_model_repair(
        current_text=post_rule_text,
        source_model_text=str(task.get("source_model_text") or ""),
        declared_failure_type=str(task.get("declared_failure_type") or task.get("failure_type") or ""),
        observed_failure_type="",
    )
    return {
        "surface_fixable_by_rule": True,
        "surface_rule_id": str(applied.rule_id or ""),
        "surface_rule_reason": str((applied.audit_dict or {}).get("reason") or ""),
        "post_rule_text": post_rule_text,
        "post_rule_source_repair_applied": bool(source_repair.get("applied")),
        "post_rule_source_repair_reason": str(source_repair.get("reason") or ""),
    }


def run_preview_omc(
    task: dict,
    model_text: str,
    *,
    backend: str = "openmodelica_docker",
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    timeout_sec: int = 60,
    stop_time: float = 10.0,
    intervals: int = 500,
) -> dict:
    fallback_model_path = Path(str(task.get("source_model_path") or "PreviewModel.mo"))
    model_name = _extract_model_name(model_text, fallback_model_path.name)

    with temporary_workspace(prefix="gf_v0_3_13_preview_") as workspace_text:
        workspace = Path(workspace_text)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=fallback_model_path,
            primary_model_name=model_name,
            source_library_path=str(task.get("source_library_path") or ""),
            source_package_name=str(task.get("source_package_name") or ""),
            source_library_model_path=str(task.get("source_library_model_path") or ""),
            source_qualified_model_name=str(task.get("source_qualified_model_name") or ""),
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        rc, output, check_ok, sim_ok = run_check_and_simulate(
            workspace=workspace,
            model_load_files=layout.model_load_files,
            model_name=layout.model_identifier,
            timeout_sec=timeout_sec,
            backend=backend,
            docker_image=docker_image,
            stop_time=stop_time,
            intervals=intervals,
            extra_model_loads=[],
        )
    diagnostic = build_diagnostic_ir_v0(
        output=output,
        check_model_pass=bool(check_ok),
        simulate_pass=bool(sim_ok),
        expected_stage=str(task.get("expected_stage") or ""),
        declared_failure_type=str(task.get("declared_failure_type") or task.get("failure_type") or ""),
    )
    return {
        "return_code": rc,
        "check_model_pass": bool(check_ok),
        "simulate_pass": bool(sim_ok),
        "diagnostic": diagnostic,
        "output_excerpt": str(output or "")[:1200],
    }


def build_preview_row(
    *,
    task: dict,
    whitelist_payload: dict,
    preview_runner: PreviewRunner | None = None,
) -> dict:
    surface = preview_surface_fix(task)
    if not surface["surface_fixable_by_rule"]:
        return {
            "task_id": str(task.get("task_id") or ""),
            **surface,
            "post_rule_residual_present": False,
            "post_rule_residual_stage": "",
            "post_rule_residual_error_type": "",
            "post_rule_residual_reason": "",
            "residual_signal_cluster_id": "",
            "residual_signal_whitelisted": False,
            "preview_admission": False,
            "preview_reason": "surface_not_fixable_by_rule",
        }
    if surface["post_rule_source_repair_applied"]:
        return {
            "task_id": str(task.get("task_id") or ""),
            **surface,
            "post_rule_residual_present": False,
            "post_rule_residual_stage": "",
            "post_rule_residual_error_type": "",
            "post_rule_residual_reason": "",
            "residual_signal_cluster_id": "",
            "residual_signal_whitelisted": False,
            "preview_admission": False,
            "preview_reason": "source_repair_would_apply_after_surface_fix",
        }

    runner = preview_runner or (lambda row, text: run_preview_omc(row, text))
    preview_result = runner(task, str(surface["post_rule_text"]))
    diagnostic = preview_result.get("diagnostic") if isinstance(preview_result.get("diagnostic"), dict) else {}
    residual_present = not (bool(preview_result.get("check_model_pass")) and bool(preview_result.get("simulate_pass")))
    matched_cluster = match_residual_signal_cluster(diagnostic=diagnostic, whitelist_payload=whitelist_payload) if residual_present else {}
    cluster_id = str(matched_cluster.get("cluster_id") or "")
    preview_admission = bool(surface["surface_fixable_by_rule"]) and residual_present and bool(cluster_id)
    return {
        "task_id": str(task.get("task_id") or ""),
        **surface,
        "post_rule_residual_present": residual_present,
        "post_rule_residual_stage": str(diagnostic.get("stage_subtype") or diagnostic.get("dominant_stage_subtype") or ""),
        "post_rule_residual_error_type": str(diagnostic.get("error_type") or ""),
        "post_rule_residual_reason": str(diagnostic.get("reason") or ""),
        "residual_signal_cluster_id": cluster_id,
        "residual_signal_whitelisted": bool(cluster_id),
        "preview_admission": preview_admission,
        "preview_reason": (
            "preview_admitted"
            if preview_admission
            else ("post_rule_success_without_residual" if not residual_present else "residual_not_in_whitelist")
        ),
        "preview_runtime": {
            "return_code": preview_result.get("return_code"),
            "check_model_pass": bool(preview_result.get("check_model_pass")),
            "simulate_pass": bool(preview_result.get("simulate_pass")),
        },
    }


def _build_summary(rows: list[dict], *, whitelist_summary_path: str, input_path: str) -> dict:
    admitted_count = sum(1 for row in rows if bool(row.get("preview_admission")))
    surface_fixable_count = sum(1 for row in rows if bool(row.get("surface_fixable_by_rule")))
    residual_present_count = sum(1 for row in rows if bool(row.get("post_rule_residual_present")))
    whitelisted_count = sum(1 for row in rows if bool(row.get("residual_signal_whitelisted")))
    cluster_counts: dict[str, int] = {}
    for row in rows:
        cluster_id = str(row.get("residual_signal_cluster_id") or "")
        if cluster_id:
            cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "input_path": str(Path(input_path).resolve()) if Path(input_path).exists() else str(input_path),
        "whitelist_summary_path": str(Path(whitelist_summary_path).resolve()) if Path(whitelist_summary_path).exists() else str(whitelist_summary_path),
        "metrics": {
            "total_rows": len(rows),
            "surface_fixable_count": surface_fixable_count,
            "post_rule_residual_present_count": residual_present_count,
            "residual_signal_whitelisted_count": whitelisted_count,
            "preview_admitted_count": admitted_count,
            "preview_admitted_rate_pct": round(100.0 * admitted_count / len(rows), 1) if rows else 0.0,
            "cluster_counts": cluster_counts,
        },
        "rows": rows,
    }


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    cluster_counts = metrics.get("cluster_counts") if isinstance(metrics.get("cluster_counts"), dict) else {}
    lines = [
        "# Trajectory Preview v0.3.13",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{metrics.get('total_rows')}`",
        f"- preview_admitted_count: `{metrics.get('preview_admitted_count')}`",
        f"- preview_admitted_rate_pct: `{metrics.get('preview_admitted_rate_pct')}`",
        "",
        "## Residual Clusters",
        "",
    ]
    for key in sorted(cluster_counts):
        lines.append(f"- `{key}`: {cluster_counts[key]}")
    lines.append("")
    return "\n".join(lines)


def build_trajectory_preview(
    *,
    input_path: str = DEFAULT_INPUT_DIR,
    whitelist_summary_path: str = f"{DEFAULT_WHITELIST_OUT_DIR}_current/summary.json",
    out_dir: str = DEFAULT_OUT_DIR,
    preview_runner: PreviewRunner | None = None,
) -> dict:
    whitelist_payload = _load_json(whitelist_summary_path)
    if not whitelist_payload:
        whitelist_payload = build_residual_signal_whitelist(out_dir=DEFAULT_WHITELIST_OUT_DIR)
    tasks = _load_tasks(input_path)
    rows = [
        build_preview_row(task=task, whitelist_payload=whitelist_payload, preview_runner=preview_runner)
        for task in tasks
    ]
    payload = _build_summary(rows, whitelist_summary_path=whitelist_summary_path, input_path=input_path)
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.13 trajectory preview gate.")
    parser.add_argument("--input-path", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--whitelist-summary", default=f"{DEFAULT_WHITELIST_OUT_DIR}_current/summary.json")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_trajectory_preview(
        input_path=str(args.input_path),
        whitelist_summary_path=str(args.whitelist_summary),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "preview_admitted_count": (payload.get("metrics") or {}).get("preview_admitted_count"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
