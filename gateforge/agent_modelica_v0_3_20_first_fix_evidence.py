from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_20_common import (
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_FIRST_FIX_RESULTS_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    apply_constrained_first_fix,
    first_attempt_signature,
    load_json,
    now_utc,
    norm,
    rerun_once,
    run_synthetic_task_live,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_20_taskset import build_v0320_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _patched_row_reason(*, patch_applied: bool, focal_patch_hit: bool, signature_advance: bool) -> str:
    if signature_advance:
        return ""
    if not patch_applied:
        return "no_patch_applied"
    if not focal_patch_hit:
        return "patch_missed_focal_token"
    return "patch_missed_focal_token"


def build_v0320_first_fix_evidence(
    *,
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"),
    results_dir: str = str(DEFAULT_FIRST_FIX_RESULTS_DIR),
    out_dir: str = str(DEFAULT_FIRST_FIX_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    if not Path(taskset_path).exists():
        build_v0320_taskset(out_dir=str(Path(taskset_path).parent))
    payload = load_json(taskset_path)
    tasks = _single_rows(payload)
    rows: list[dict] = []
    advance_mode_counts: dict[str, int] = {}
    non_advance_reason_counts: dict[str, int] = {}
    admitted_tasks: list[dict] = []
    for task in tasks:
        initial = run_synthetic_task_live(
            task=task,
            result_dir=results_dir,
            evaluation_label="v0320_single_first_failure",
            max_rounds=1,
            timeout_sec=timeout_sec,
        )
        initial_detail = initial.get("detail") if isinstance(initial.get("detail"), dict) else {}
        first_signature, first_snapshot = first_attempt_signature(initial_detail)
        patched_text, patch_audit = apply_constrained_first_fix(
            current_text=norm(task.get("mutated_model_text")),
            patch_type=norm(task.get("patch_type")),
            wrong_symbol=norm(task.get("wrong_symbol")),
            candidate_key=task.get("candidate_key"),
        )
        post = rerun_once(
            task_id=f"{norm(task.get('task_id'))}__patched",
            model_text=patched_text,
            result_dir=results_dir,
            evaluation_label="v0320_single_after_first_fix",
            timeout_sec=timeout_sec,
        ) if bool(patch_audit.get("applied")) else {"detail": {}, "result_json_path": ""}
        post_detail = post.get("detail") if isinstance(post.get("detail"), dict) else {}
        post_signature, post_snapshot = first_attempt_signature(post_detail)
        post_resolved = norm(post_detail.get("executor_status")).upper() == "PASS"
        focal_patch_hit = bool(patch_audit.get("applied") and norm(patch_audit.get("wrong_symbol")) == norm(task.get("wrong_symbol")))
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
        non_advance_reason = _patched_row_reason(
            patch_applied=bool(patch_audit.get("applied")),
            focal_patch_hit=focal_patch_hit,
            signature_advance=signature_advance,
        )
        row = {
            "task_id": task.get("task_id"),
            "complexity_tier": task.get("complexity_tier"),
            "patch_type": task.get("patch_type"),
            "initial_result_json_path": initial.get("result_json_path"),
            "post_patch_result_json_path": post.get("result_json_path"),
            "initial_executor_status": initial_detail.get("executor_status"),
            "initial_signature": first_signature,
            "initial_snapshot": first_snapshot,
            "patch_applied": bool(patch_audit.get("applied")),
            "selected_candidate": patch_audit.get("selected_candidate"),
            "candidate_symbols": patch_audit.get("candidate_symbols"),
            "focal_patch_hit": focal_patch_hit,
            "post_patch_executor_status": post_detail.get("executor_status"),
            "post_patch_signature": post_signature,
            "post_patch_snapshot": post_snapshot,
            "signature_advance": signature_advance,
            "secondary_error_exposed_early": secondary_error_exposed_early,
            "advance_mode": advance_mode,
            "signature_advance_not_fired_reason": non_advance_reason,
            "post_patch_stage2_retained": (
                norm(post_snapshot.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference"
                and norm(post_snapshot.get("error_subtype")) == "undefined_symbol"
            ),
        }
        rows.append(row)
        advance_mode_counts[advance_mode] = advance_mode_counts.get(advance_mode, 0) + 1
        if non_advance_reason:
            non_advance_reason_counts[non_advance_reason] = non_advance_reason_counts.get(non_advance_reason, 0) + 1
        if bool(row.get("patch_applied")) and bool(row.get("signature_advance")):
            admitted_task = dict(task)
            admitted_task["v0_3_20_first_fix_row"] = row
            admitted_tasks.append(admitted_task)
    task_count = len(rows)
    patch_applied_count = sum(1 for row in rows if bool(row.get("patch_applied")))
    focal_patch_hit_count = sum(1 for row in rows if bool(row.get("focal_patch_hit")))
    signature_advance_count = sum(1 for row in rows if bool(row.get("signature_advance")))
    post_patch_stage2_retained_count = sum(1 for row in rows if bool(row.get("post_patch_stage2_retained")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "taskset_path": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
        "task_count": task_count,
        "patch_applied_count": patch_applied_count,
        "patch_applied_rate_pct": round(100.0 * patch_applied_count / float(task_count), 1) if task_count else 0.0,
        "focal_patch_hit_count": focal_patch_hit_count,
        "focal_patch_hit_rate_pct": round(100.0 * focal_patch_hit_count / float(task_count), 1) if task_count else 0.0,
        "signature_advance_count": signature_advance_count,
        "signature_advance_rate_pct": round(100.0 * signature_advance_count / float(task_count), 1) if task_count else 0.0,
        "post_patch_stage2_retention_count": post_patch_stage2_retained_count,
        "post_patch_stage2_retention_rate_pct": round(100.0 * post_patch_stage2_retained_count / float(task_count), 1) if task_count else 0.0,
        "advance_mode_counts": advance_mode_counts,
        "signature_advance_not_fired_reason_counts": non_advance_reason_counts,
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
                "# v0.3.20 First-Fix Evidence",
                "",
                f"- status: `{summary.get('status')}`",
                f"- patch_applied_rate_pct: `{summary.get('patch_applied_rate_pct')}`",
                f"- signature_advance_rate_pct: `{summary.get('signature_advance_rate_pct')}`",
                f"- admitted_task_count: `{summary.get('admitted_task_count')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "admitted_taskset": admitted_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.20 single-mismatch first-fix evidence flow.")
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"))
    parser.add_argument("--results-dir", default=str(DEFAULT_FIRST_FIX_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_v0320_first_fix_evidence(
        taskset_path=str(args.taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "signature_advance_rate_pct": summary.get("signature_advance_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
