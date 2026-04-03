from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_21_common import (
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_DUAL_RECHECK_RESULTS_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
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
from .agent_modelica_v0_3_21_first_fix_evidence import build_v0321_first_fix_evidence
from .agent_modelica_v0_3_21_surface_index import build_v0321_surface_index
from .agent_modelica_v0_3_21_taskset import build_v0321_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dual_recheck"


def _dual_rows(payload: dict) -> list[dict]:
    rows = payload.get("dual_sidecar_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_v0321_dual_recheck(
    *,
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"),
    first_fix_summary_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"),
    results_dir: str = str(DEFAULT_DUAL_RECHECK_RESULTS_DIR),
    out_dir: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    if not Path(surface_index_path).exists():
        build_v0321_surface_index(out_dir=str(Path(surface_index_path).parent))
    if not Path(first_fix_summary_path).exists():
        build_v0321_first_fix_evidence(surface_index_path=surface_index_path, out_dir=str(Path(first_fix_summary_path).parent))
    if not Path(taskset_path).exists():
        build_v0321_taskset(surface_index_path=surface_index_path, out_dir=str(Path(taskset_path).parent))
    first_fix_summary = load_json(first_fix_summary_path)
    taskset = load_json(taskset_path)
    dual_tasks = _dual_rows(taskset)
    first_fix_ready = (
        float(first_fix_summary.get("candidate_contains_canonical_rate_pct") or 0.0) >= 80.0
        and float(first_fix_summary.get("patch_applied_rate_pct") or 0.0) >= 70.0
        and float(first_fix_summary.get("signature_advance_rate_pct") or 0.0) >= 50.0
    )
    rows: list[dict] = []
    if first_fix_ready:
        for task in dual_tasks:
            initial = run_synthetic_task_live(
                task=task,
                result_dir=results_dir,
                evaluation_label="v0321_dual_initial",
                max_rounds=1,
                timeout_sec=timeout_sec,
            )
            initial_detail = initial.get("detail") if isinstance(initial.get("detail"), dict) else {}
            first_signature, first_snapshot = first_attempt_signature(initial_detail)
            first_step = (task.get("repair_steps") or [{}])[0]
            patched_once_text, first_patch_audit = apply_discovery_first_fix(
                current_text=norm(task.get("mutated_model_text")),
                patch_type=norm(first_step.get("patch_type")),
                wrong_symbol=norm(first_step.get("wrong_symbol")),
                component_type=norm(first_step.get("component_type")),
                canonical_symbol=norm(first_step.get("correct_symbol")),
                class_candidates=list(first_step.get("class_path_candidates") or []),
                parameter_records=list(first_step.get("candidate_parameter_records") or []),
            )
            after_first = rerun_once(
                task_id=f"{norm(task.get('task_id'))}__after_first_fix",
                model_text=patched_once_text if first_patch_audit.get("applied") else norm(task.get("mutated_model_text")),
                result_dir=results_dir,
                evaluation_label="v0321_dual_after_first_fix",
                timeout_sec=timeout_sec,
            ) if bool(first_patch_audit.get("applied")) else {"detail": {}, "result_json_path": ""}
            after_first_detail = after_first.get("detail") if isinstance(after_first.get("detail"), dict) else {}
            second_signature, second_snapshot = first_attempt_signature(after_first_detail)
            second_residual_exposed = bool(
                norm(second_snapshot.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference"
                and norm(second_snapshot.get("error_subtype")) == "undefined_symbol"
                and bool(first_signature)
                and bool(second_signature)
                and first_signature != second_signature
            )
            second_residual_undefined_symbol = bool(
                norm(second_snapshot.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference"
                and norm(second_snapshot.get("error_subtype")) == "undefined_symbol"
            )
            second_patch_audit = {"applied": False, "reason": "second_residual_not_exposed"}
            final_detail = {}
            final_signature = ""
            if second_residual_exposed and len(task.get("repair_steps") or []) >= 2:
                second_step = (task.get("repair_steps") or [])[1]
                patched_twice_text, second_patch_audit = apply_discovery_first_fix(
                    current_text=patched_once_text,
                    patch_type=norm(second_step.get("patch_type")),
                    wrong_symbol=norm(second_step.get("wrong_symbol")),
                    component_type=norm(second_step.get("component_type")),
                    canonical_symbol=norm(second_step.get("correct_symbol")),
                    class_candidates=list(second_step.get("class_path_candidates") or []),
                    parameter_records=list(second_step.get("candidate_parameter_records") or []),
                )
                final = rerun_once(
                    task_id=f"{norm(task.get('task_id'))}__after_second_fix",
                    model_text=patched_twice_text if second_patch_audit.get("applied") else patched_once_text,
                    result_dir=results_dir,
                    evaluation_label="v0321_dual_after_second_fix",
                    timeout_sec=timeout_sec,
                )
                final_detail = final.get("detail") if isinstance(final.get("detail"), dict) else {}
                final_signature, _ = first_attempt_signature(final_detail)
            rows.append(
                {
                    "task_id": task.get("task_id"),
                    "placement_kind": task.get("placement_kind"),
                    "initial_signature": first_signature,
                    "first_patch_selected_candidate": first_patch_audit.get("selected_candidate"),
                    "first_patch_top1_is_canonical": bool(first_patch_audit.get("candidate_top1_is_canonical")),
                    "after_first_signature": second_signature,
                    "second_residual_exposed": second_residual_exposed,
                    "second_residual_undefined_symbol": second_residual_undefined_symbol,
                    "second_patch_selected_candidate": second_patch_audit.get("selected_candidate"),
                    "second_patch_top1_is_canonical": bool(second_patch_audit.get("candidate_top1_is_canonical")),
                    "final_executor_status": final_detail.get("executor_status") if isinstance(final_detail, dict) else "",
                    "final_signature": final_signature,
                    "full_dual_resolution": norm(final_detail.get("executor_status")).upper() == "PASS",
                }
            )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if first_fix_ready else "SKIPPED",
        "first_fix_discovery_ready": first_fix_ready,
        "task_count": len(rows),
        "same_component_task_count": sum(1 for row in rows if norm(row.get("placement_kind")) == "same_component_dual_mismatch"),
        "neighbor_component_task_count": sum(1 for row in rows if norm(row.get("placement_kind")) == "neighbor_component_dual_mismatch"),
        "second_residual_exposed_count": sum(1 for row in rows if bool(row.get("second_residual_exposed"))),
        "second_residual_undefined_symbol_count": sum(1 for row in rows if bool(row.get("second_residual_undefined_symbol"))),
        "full_dual_resolution_count": sum(1 for row in rows if bool(row.get("full_dual_resolution"))),
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.21 Dual Recheck",
                "",
                f"- status: `{summary.get('status')}`",
                f"- first_fix_discovery_ready: `{summary.get('first_fix_discovery_ready')}`",
                f"- second_residual_exposed_count: `{summary.get('second_residual_exposed_count')}`",
                f"- full_dual_resolution_count: `{summary.get('full_dual_resolution_count')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.21 dual-mismatch discovery recheck.")
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"))
    parser.add_argument("--first-fix-summary", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"))
    parser.add_argument("--results-dir", default=str(DEFAULT_DUAL_RECHECK_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_v0321_dual_recheck(
        surface_index_path=str(args.surface_index),
        first_fix_summary_path=str(args.first_fix_summary),
        taskset_path=str(args.taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "full_dual_resolution_count": payload.get("full_dual_resolution_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
