from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_21_common import (
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_FIRST_FIX_RESULTS_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    apply_discovery_first_fix,
    first_attempt_signature,
    load_json,
    now_utc,
    norm,
    rerun_once,
    run_synthetic_task_live,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_21_surface_index import build_v0321_surface_index
from .agent_modelica_v0_3_21_taskset import build_v0321_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _task_fixture_detail(task: dict, key: str) -> dict:
    payload = task.get(key)
    return payload if isinstance(payload, dict) else {}


def _run_initial(task: dict, results_dir: str, timeout_sec: int) -> tuple[dict, str]:
    fixture = _task_fixture_detail(task, "v0_3_21_fixture_initial_detail")
    if fixture:
        return fixture, ""
    initial = run_synthetic_task_live(
        task=task,
        result_dir=results_dir,
        evaluation_label="v0321_single_first_failure",
        max_rounds=1,
        timeout_sec=timeout_sec,
    )
    detail = initial.get("detail") if isinstance(initial.get("detail"), dict) else {}
    return detail, norm(initial.get("result_json_path"))


def _run_post(task: dict, patched_text: str, selected_is_canonical: bool, results_dir: str, timeout_sec: int) -> tuple[dict, str]:
    fixture_key = "v0_3_21_fixture_post_detail" if selected_is_canonical else "v0_3_21_fixture_post_wrong_detail"
    fixture = _task_fixture_detail(task, fixture_key)
    if fixture:
        return fixture, ""
    post = rerun_once(
        task_id=f"{norm(task.get('task_id'))}__patched",
        model_text=patched_text,
        result_dir=results_dir,
        evaluation_label="v0321_single_after_first_fix",
        timeout_sec=timeout_sec,
    )
    detail = post.get("detail") if isinstance(post.get("detail"), dict) else {}
    return detail, norm(post.get("result_json_path"))


def build_v0321_first_fix_evidence(
    *,
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"),
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"),
    results_dir: str = str(DEFAULT_FIRST_FIX_RESULTS_DIR),
    out_dir: str = str(DEFAULT_FIRST_FIX_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    if not Path(surface_index_path).exists():
        build_v0321_surface_index(out_dir=str(Path(surface_index_path).parent))
    if not Path(taskset_path).exists():
        build_v0321_taskset(surface_index_path=surface_index_path, out_dir=str(Path(taskset_path).parent))
    taskset = load_json(taskset_path)
    tasks = _single_rows(taskset)
    rows: list[dict] = []
    reason_counts: dict[str, int] = {}
    advance_mode_counts: dict[str, int] = {}
    admitted_tasks: list[dict] = []
    parameter_top1_hits = 0
    parameter_task_count = 0
    class_top1_hits = 0
    class_task_count = 0
    for task in tasks:
        initial_detail, initial_result_path = _run_initial(task, results_dir, timeout_sec)
        first_signature, first_snapshot = first_attempt_signature(initial_detail)
        canonical_symbol = norm(task.get("correct_symbol"))
        patch_type = norm(task.get("patch_type"))
        patched_text, patch_audit = apply_discovery_first_fix(
            current_text=norm(task.get("mutated_model_text")),
            patch_type=patch_type,
            wrong_symbol=norm(task.get("wrong_symbol")),
            component_type=norm(task.get("component_type")),
            canonical_symbol=canonical_symbol,
            class_candidates=list(task.get("class_path_candidates") or []),
            parameter_records=list(task.get("candidate_parameter_records") or []),
        )
        selected_is_canonical = bool(patch_audit.get("candidate_top1_is_canonical"))
        post_detail, post_result_path = _run_post(task, patched_text, selected_is_canonical, results_dir, timeout_sec) if bool(patch_audit.get("applied")) else ({}, "")
        post_signature, post_snapshot = first_attempt_signature(post_detail)
        post_resolved = norm(post_detail.get("executor_status")).upper() == "PASS"
        focal_patch_hit = bool(patch_audit.get("applied") and norm(task.get("wrong_symbol")))
        secondary_error_exposed_early = bool(
            not post_resolved
            and norm(post_snapshot.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference"
            and norm(post_snapshot.get("error_subtype")) == "undefined_symbol"
            and bool(first_signature)
            and bool(post_signature)
            and first_signature != post_signature
        )
        signature_advance = bool(post_resolved or secondary_error_exposed_early or (bool(first_signature) and bool(post_signature) and first_signature != post_signature))
        if post_resolved:
            advance_mode = "resolved_after_first_fix"
        elif secondary_error_exposed_early:
            advance_mode = "secondary_error_exposed_early"
        elif signature_advance:
            advance_mode = "signature_advanced_other"
        else:
            advance_mode = "signature_stagnated"
        if not signature_advance:
            if not bool(patch_audit.get("candidate_contains_canonical")):
                non_advance_reason = "candidate_set_missing_canonical"
            elif not bool(patch_audit.get("candidate_top1_is_canonical")):
                non_advance_reason = "wrong_candidate_selected"
            elif not focal_patch_hit:
                non_advance_reason = "patch_missed_focal_token"
            else:
                non_advance_reason = "patch_missed_focal_token"
        else:
            non_advance_reason = ""
        if patch_type == "replace_parameter_name":
            parameter_task_count += 1
            if bool(patch_audit.get("candidate_top1_is_canonical")):
                parameter_top1_hits += 1
        else:
            class_task_count += 1
            if bool(patch_audit.get("candidate_top1_is_canonical")):
                class_top1_hits += 1
        row = {
            "task_id": task.get("task_id"),
            "complexity_tier": task.get("complexity_tier"),
            "patch_type": patch_type,
            "initial_result_json_path": initial_result_path,
            "post_patch_result_json_path": post_result_path,
            "initial_signature": first_signature,
            "initial_snapshot": first_snapshot,
            "selected_candidate": patch_audit.get("selected_candidate"),
            "candidate_symbols": patch_audit.get("candidate_symbols"),
            "candidate_contains_canonical": bool(patch_audit.get("candidate_contains_canonical")),
            "candidate_top1_is_canonical": bool(patch_audit.get("candidate_top1_is_canonical")),
            "patch_applied": bool(patch_audit.get("applied")),
            "focal_patch_hit": focal_patch_hit,
            "post_patch_signature": post_signature,
            "post_patch_snapshot": post_snapshot,
            "signature_advance": signature_advance,
            "advance_mode": advance_mode,
            "signature_advance_not_fired_reason": non_advance_reason,
        }
        rows.append(row)
        advance_mode_counts[advance_mode] = advance_mode_counts.get(advance_mode, 0) + 1
        if non_advance_reason:
            reason_counts[non_advance_reason] = reason_counts.get(non_advance_reason, 0) + 1
        if bool(row.get("patch_applied")) and bool(row.get("signature_advance")):
            admitted_task = dict(task)
            admitted_task["v0_3_21_first_fix_row"] = row
            admitted_tasks.append(admitted_task)
    task_count = len(rows)
    candidate_contains = sum(1 for row in rows if bool(row.get("candidate_contains_canonical")))
    candidate_top1 = sum(1 for row in rows if bool(row.get("candidate_top1_is_canonical")))
    patch_applied = sum(1 for row in rows if bool(row.get("patch_applied")))
    focal_patch_hit = sum(1 for row in rows if bool(row.get("focal_patch_hit")))
    signature_advance = sum(1 for row in rows if bool(row.get("signature_advance")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "task_count": task_count,
        "candidate_contains_canonical_count": candidate_contains,
        "candidate_contains_canonical_rate_pct": round(100.0 * candidate_contains / float(task_count), 1) if task_count else 0.0,
        "candidate_top1_canonical_count": candidate_top1,
        "candidate_top1_canonical_rate_pct": round(100.0 * candidate_top1 / float(task_count), 1) if task_count else 0.0,
        "parameter_discovery_top1_canonical_rate_pct": round(100.0 * parameter_top1_hits / float(parameter_task_count), 1) if parameter_task_count else 0.0,
        "class_path_discovery_top1_canonical_rate_pct": round(100.0 * class_top1_hits / float(class_task_count), 1) if class_task_count else 0.0,
        "patch_applied_count": patch_applied,
        "patch_applied_rate_pct": round(100.0 * patch_applied / float(task_count), 1) if task_count else 0.0,
        "focal_patch_hit_count": focal_patch_hit,
        "focal_patch_hit_rate_pct": round(100.0 * focal_patch_hit / float(task_count), 1) if task_count else 0.0,
        "signature_advance_count": signature_advance,
        "signature_advance_rate_pct": round(100.0 * signature_advance / float(task_count), 1) if task_count else 0.0,
        "advance_mode_counts": advance_mode_counts,
        "signature_advance_not_fired_reason_counts": reason_counts,
        "admitted_task_count": len(admitted_tasks),
        "rows": rows,
    }
    admitted_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if admitted_tasks else "EMPTY",
        "task_count": len(admitted_tasks),
        "task_ids": [norm(task.get("task_id")) for task in admitted_tasks],
        "tasks": admitted_tasks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "admitted_taskset.json", admitted_payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.21 First-Fix Discovery Evidence",
                "",
                f"- status: `{summary.get('status')}`",
                f"- candidate_contains_canonical_rate_pct: `{summary.get('candidate_contains_canonical_rate_pct')}`",
                f"- candidate_top1_canonical_rate_pct: `{summary.get('candidate_top1_canonical_rate_pct')}`",
                f"- signature_advance_rate_pct: `{summary.get('signature_advance_rate_pct')}`",
                f"- admitted_task_count: `{summary.get('admitted_task_count')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "admitted_taskset": admitted_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.21 single-mismatch discovery evidence flow.")
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"))
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"))
    parser.add_argument("--results-dir", default=str(DEFAULT_FIRST_FIX_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_v0321_first_fix_evidence(
        surface_index_path=str(args.surface_index),
        taskset_path=str(args.taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "signature_advance_rate_pct": summary.get("signature_advance_rate_pct"), "candidate_top1_canonical_rate_pct": summary.get("candidate_top1_canonical_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
