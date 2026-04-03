from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_23_common import (
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_DUAL_RECHECK_RESULTS_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_TARGET_MANIFEST_OUT_DIR,
    SCHEMA_PREFIX,
    TARGET_ERROR_SUBTYPE,
    TARGET_STAGE_SUBTYPE,
    apply_interface_first_fix,
    first_attempt_signature,
    load_json,
    now_utc,
    norm,
    rerun_once,
    run_synthetic_task_live,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_23_first_fix_evidence import build_v0323_first_fix_evidence
from .agent_modelica_v0_3_23_target_manifest import build_v0323_target_manifest


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dual_recheck"


def _dual_rows(payload: dict) -> list[dict]:
    rows = payload.get("dual_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_v0323_dual_recheck(
    *,
    manifest_path: str = str(DEFAULT_TARGET_MANIFEST_OUT_DIR / "manifest.json"),
    first_fix_summary_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    results_dir: str = str(DEFAULT_DUAL_RECHECK_RESULTS_DIR),
    out_dir: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    if not Path(manifest_path).exists():
        build_v0323_target_manifest(out_dir=str(Path(manifest_path).parent))
    if not Path(first_fix_summary_path).exists():
        build_v0323_first_fix_evidence(manifest_path=manifest_path, out_dir=str(Path(first_fix_summary_path).parent))
    first_fix = load_json(first_fix_summary_path)
    payload = load_json(manifest_path)
    dual_tasks = _dual_rows(payload)
    first_fix_ready = (
        float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) >= 80.0
        and float(first_fix.get("patch_applied_rate_pct") or 0.0) >= 70.0
        and float(first_fix.get("signature_advance_rate_pct") or 0.0) >= 50.0
        and float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) <= 20.0
    )
    rows: list[dict] = []
    if first_fix_ready:
        for task in dual_tasks:
            initial = run_synthetic_task_live(
                task=task,
                result_dir=results_dir,
                evaluation_label="v0323_dual_initial",
                max_rounds=1,
                timeout_sec=timeout_sec,
            )
            initial_detail = initial.get("detail") if isinstance(initial.get("detail"), dict) else {}
            first_signature, _ = first_attempt_signature(initial_detail)
            first_step = (task.get("repair_steps") or [{}])[0]
            patched_once_text, first_patch_audit = apply_interface_first_fix(
                current_text=norm(task.get("mutated_model_text")),
                patch_type=norm(first_step.get("patch_type")),
                wrong_symbol=norm(first_step.get("wrong_symbol")),
                candidate_key=norm(first_step.get("candidate_key")),
            )
            after_first = rerun_once(
                task_id=f"{norm(task.get('task_id'))}__after_first_fix",
                model_text=patched_once_text if first_patch_audit.get("applied") else norm(task.get("mutated_model_text")),
                result_dir=results_dir,
                evaluation_label="v0323_dual_after_first_fix",
                timeout_sec=timeout_sec,
            ) if bool(first_patch_audit.get("applied")) else {"detail": {}, "result_json_path": ""}
            after_first_detail = after_first.get("detail") if isinstance(after_first.get("detail"), dict) else {}
            second_signature, second_snapshot = first_attempt_signature(after_first_detail)
            second_residual_exposed = bool(
                norm(second_snapshot.get("dominant_stage_subtype")) == TARGET_STAGE_SUBTYPE
                and norm(second_snapshot.get("error_subtype")) == TARGET_ERROR_SUBTYPE
                and bool(first_signature)
                and bool(second_signature)
                and first_signature != second_signature
            )
            second_residual_local_interface_retained = second_residual_exposed
            second_patch_audit = {"applied": False}
            final_detail = {}
            if second_residual_exposed and len(task.get("repair_steps") or []) >= 2:
                second_step = (task.get("repair_steps") or [])[1]
                patched_twice_text, second_patch_audit = apply_interface_first_fix(
                    current_text=patched_once_text,
                    patch_type=norm(second_step.get("patch_type")),
                    wrong_symbol=norm(second_step.get("wrong_symbol")),
                    candidate_key=norm(second_step.get("candidate_key")),
                )
                final = rerun_once(
                    task_id=f"{norm(task.get('task_id'))}__after_second_fix",
                    model_text=patched_twice_text if second_patch_audit.get("applied") else patched_once_text,
                    result_dir=results_dir,
                    evaluation_label="v0323_dual_after_second_fix",
                    timeout_sec=timeout_sec,
                )
                final_detail = final.get("detail") if isinstance(final.get("detail"), dict) else {}
            rows.append(
                {
                    "task_id": task.get("task_id"),
                    "complexity_tier": task.get("complexity_tier"),
                    "component_family": task.get("component_family"),
                    "placement_kind": task.get("placement_kind"),
                    "second_residual_exposed": second_residual_exposed,
                    "second_residual_local_interface_retained": second_residual_local_interface_retained,
                    "full_dual_resolution": norm(final_detail.get("executor_status")).upper() == "PASS",
                }
            )
    same_cluster_rows = [row for row in rows if norm(row.get("placement_kind")) in {"same_component_dual_mismatch", "same_local_cluster_dual_mismatch"}]
    same_count = len(same_cluster_rows)
    same_exposed = sum(1 for row in same_cluster_rows if bool(row.get("second_residual_exposed")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if first_fix_ready else "SKIPPED",
        "first_fix_ready": first_fix_ready,
        "task_count": len(rows),
        "second_residual_exposed_count": sum(1 for row in rows if bool(row.get("second_residual_exposed"))),
        "second_residual_local_interface_retained_count": sum(1 for row in rows if bool(row.get("second_residual_local_interface_retained"))),
        "full_dual_resolution_count": sum(1 for row in rows if bool(row.get("full_dual_resolution"))),
        "same_cluster_second_residual_rate_pct": round(100.0 * same_exposed / float(same_count), 1) if same_count else 0.0,
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.23 Dual Recheck",
                "",
                f"- status: `{summary.get('status')}`",
                f"- first_fix_ready: `{summary.get('first_fix_ready')}`",
                f"- same_cluster_second_residual_rate_pct: `{summary.get('same_cluster_second_residual_rate_pct')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.23 dual recheck.")
    parser.add_argument("--manifest", default=str(DEFAULT_TARGET_MANIFEST_OUT_DIR / "manifest.json"))
    parser.add_argument("--first-fix-summary", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--results-dir", default=str(DEFAULT_DUAL_RECHECK_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_v0323_dual_recheck(
        manifest_path=str(args.manifest),
        first_fix_summary_path=str(args.first_fix_summary),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "same_cluster_second_residual_rate_pct": payload.get("same_cluster_second_residual_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
