from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_22_common import (
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_FIRST_FIX_RESULTS_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
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
from .agent_modelica_v0_3_22_surface_export_audit import build_v0322_surface_export_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _rate_rows(rows: list[dict]) -> dict[str, float | int]:
    count = len(rows)
    candidate_contains = sum(1 for row in rows if bool(row.get("candidate_contains_canonical")))
    candidate_top1 = sum(1 for row in rows if bool(row.get("candidate_top1_is_canonical")))
    patch_applied = sum(1 for row in rows if bool(row.get("patch_applied")))
    signature_advance = sum(1 for row in rows if bool(row.get("signature_advance")))
    secondary = sum(1 for row in rows if bool(row.get("secondary_error_exposed_early")))
    return {
        "task_count": count,
        "candidate_contains_canonical_rate_pct": round(100.0 * candidate_contains / float(count), 1) if count else 0.0,
        "candidate_top1_canonical_rate_pct": round(100.0 * candidate_top1 / float(count), 1) if count else 0.0,
        "patch_applied_rate_pct": round(100.0 * patch_applied / float(count), 1) if count else 0.0,
        "signature_advance_rate_pct": round(100.0 * signature_advance / float(count), 1) if count else 0.0,
        "secondary_error_exposed_early_rate_pct": round(100.0 * secondary / float(count), 1) if count else 0.0,
    }


def _group_breakdown(rows: list[dict], key: str) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        groups.setdefault(value, []).append(row)
    return {group: _rate_rows(group_rows) for group, group_rows in groups.items()}


def build_v0322_first_fix_evidence(
    *,
    active_taskset_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"),
    results_dir: str = str(DEFAULT_FIRST_FIX_RESULTS_DIR),
    out_dir: str = str(DEFAULT_FIRST_FIX_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    if not Path(active_taskset_path).exists():
        build_v0322_surface_export_audit(out_dir=str(Path(active_taskset_path).parent))
    payload = load_json(active_taskset_path)
    tasks = _single_rows(payload)
    rows: list[dict] = []
    advance_mode_counts: dict[str, int] = {}
    non_advance_reason_counts: dict[str, int] = {}
    admitted_tasks: list[dict] = []
    parameter_top1_hits = 0
    parameter_task_count = 0
    class_top1_hits = 0
    class_task_count = 0
    for task in tasks:
        initial = run_synthetic_task_live(
            task=task,
            result_dir=results_dir,
            evaluation_label="v0322_single_first_failure",
            max_rounds=1,
            timeout_sec=timeout_sec,
        )
        initial_detail = initial.get("detail") if isinstance(initial.get("detail"), dict) else {}
        first_signature, first_snapshot = first_attempt_signature(initial_detail)
        patch_type = norm(task.get("patch_type"))
        patched_text, patch_audit = apply_discovery_first_fix(
            current_text=norm(task.get("mutated_model_text")),
            patch_type=patch_type,
            wrong_symbol=norm(task.get("wrong_symbol")),
            component_type=norm(task.get("component_type")),
            canonical_symbol=norm(task.get("correct_symbol")),
            class_candidates=list(task.get("class_path_candidates") or []),
            parameter_records=list(task.get("candidate_parameter_records") or []),
        )
        post = rerun_once(
            task_id=f"{norm(task.get('task_id'))}__patched",
            model_text=patched_text,
            result_dir=results_dir,
            evaluation_label="v0322_single_after_first_fix",
            timeout_sec=timeout_sec,
        ) if bool(patch_audit.get("applied")) else {"detail": {}, "result_json_path": ""}
        post_detail = post.get("detail") if isinstance(post.get("detail"), dict) else {}
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
            non_advance_reason = ""
        elif secondary_error_exposed_early:
            advance_mode = "secondary_error_exposed_early"
            non_advance_reason = ""
        elif signature_advance:
            advance_mode = "signature_advanced_other"
            non_advance_reason = ""
        else:
            advance_mode = "signature_stagnated"
            if norm(task.get("candidate_provenance")) != "omc_export":
                non_advance_reason = "surface_export_missing_canonical"
            elif not bool(patch_audit.get("candidate_contains_canonical")):
                non_advance_reason = "candidate_set_missing_canonical"
            elif not bool(patch_audit.get("candidate_top1_is_canonical")):
                non_advance_reason = "wrong_candidate_selected"
            else:
                non_advance_reason = "patch_missed_focal_token"
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
            "component_family": task.get("component_family"),
            "patch_type": patch_type,
            "candidate_provenance": task.get("candidate_provenance"),
            "initial_result_json_path": initial.get("result_json_path"),
            "post_patch_result_json_path": post.get("result_json_path"),
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
            "secondary_error_exposed_early": secondary_error_exposed_early,
            "advance_mode": advance_mode,
            "signature_advance_not_fired_reason": non_advance_reason,
        }
        rows.append(row)
        advance_mode_counts[advance_mode] = advance_mode_counts.get(advance_mode, 0) + 1
        if non_advance_reason:
            non_advance_reason_counts[non_advance_reason] = non_advance_reason_counts.get(non_advance_reason, 0) + 1
        if bool(row.get("patch_applied")) and bool(row.get("signature_advance")):
            admitted = dict(task)
            admitted["v0_3_22_first_fix_row"] = row
            admitted_tasks.append(admitted)
    task_count = len(rows)
    candidate_contains = sum(1 for row in rows if bool(row.get("candidate_contains_canonical")))
    candidate_top1 = sum(1 for row in rows if bool(row.get("candidate_top1_is_canonical")))
    patch_applied_count = sum(1 for row in rows if bool(row.get("patch_applied")))
    focal_patch_hit_count = sum(1 for row in rows if bool(row.get("focal_patch_hit")))
    signature_advance_count = sum(1 for row in rows if bool(row.get("signature_advance")))
    secondary_count = sum(1 for row in rows if bool(row.get("secondary_error_exposed_early")))
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
        "patch_applied_count": patch_applied_count,
        "patch_applied_rate_pct": round(100.0 * patch_applied_count / float(task_count), 1) if task_count else 0.0,
        "focal_patch_hit_count": focal_patch_hit_count,
        "focal_patch_hit_rate_pct": round(100.0 * focal_patch_hit_count / float(task_count), 1) if task_count else 0.0,
        "signature_advance_count": signature_advance_count,
        "signature_advance_rate_pct": round(100.0 * signature_advance_count / float(task_count), 1) if task_count else 0.0,
        "secondary_error_exposed_early_count": secondary_count,
        "secondary_error_exposed_early_rate_pct": round(100.0 * secondary_count / float(task_count), 1) if task_count else 0.0,
        "advance_mode_counts": advance_mode_counts,
        "signature_advance_not_fired_reason_counts": non_advance_reason_counts,
        "complexity_tier_breakdown": _group_breakdown(rows, "complexity_tier"),
        "patch_type_breakdown": _group_breakdown(rows, "patch_type"),
        "component_family_breakdown": _group_breakdown(rows, "component_family"),
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
                "# v0.3.22 First-Fix Evidence",
                "",
                f"- status: `{summary.get('status')}`",
                f"- candidate_contains_canonical_rate_pct: `{summary.get('candidate_contains_canonical_rate_pct')}`",
                f"- candidate_top1_canonical_rate_pct: `{summary.get('candidate_top1_canonical_rate_pct')}`",
                f"- patch_applied_rate_pct: `{summary.get('patch_applied_rate_pct')}`",
                f"- signature_advance_rate_pct: `{summary.get('signature_advance_rate_pct')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "admitted_taskset": admitted_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.22 expanded first-fix evidence flow.")
    parser.add_argument("--active-taskset", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"))
    parser.add_argument("--results-dir", default=str(DEFAULT_FIRST_FIX_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_v0322_first_fix_evidence(
        active_taskset_path=str(args.active_taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "candidate_top1_canonical_rate_pct": summary.get("candidate_top1_canonical_rate_pct"), "signature_advance_rate_pct": summary.get("signature_advance_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
