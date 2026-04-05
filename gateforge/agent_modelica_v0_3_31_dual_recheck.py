from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_31_common import (
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    apply_medium_redeclare_discovery_patch,
    fixture_dry_run_result,
    load_json,
    medium_redeclare_target_hit,
    norm,
    now_utc,
    parse_canonical_rhs_from_repair_step,
    rank_medium_rhs_candidates,
    run_dry_run,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_31_first_fix_evidence import build_v0331_first_fix_evidence


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dual_recheck"


def _surface_rows_by_source(payload: dict) -> dict[str, dict]:
    rows = payload.get("task_rows")
    mapping: dict[str, dict] = {}
    if not isinstance(rows, list):
        return mapping
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_id = norm(row.get("source_id"))
        if source_id and source_id not in mapping:
            mapping[source_id] = row
    return mapping


def _dual_rows(payload: dict) -> list[dict]:
    rows = payload.get("dual_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _run_or_fixture(*, model_name: str, model_text: str, phase: str, use_fixture_only: bool) -> dict:
    if use_fixture_only:
        return fixture_dry_run_result(phase=phase)
    return run_dry_run(model_name, model_text)


def _subtype_metrics(rows: list[dict], subtype: str) -> dict:
    selected = [row for row in rows if norm(row.get("component_subtype")) == norm(subtype)]
    count = len(selected)
    if not count:
        return {"task_count": 0}
    return {
        "task_count": count,
        "post_first_fix_target_bucket_hit_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("post_first_fix_target_bucket_hit"))) / float(count), 1),
        "second_residual_medium_redeclare_retained_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("second_residual_medium_redeclare_retained"))) / float(count), 1),
        "dual_full_resolution_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("dual_full_resolution"))) / float(count), 1),
    }


def build_v0331_dual_recheck(
    *,
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    active_taskset_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"),
    surface_index_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"),
    out_dir: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(first_fix_path).exists():
        build_v0331_first_fix_evidence(out_dir=str(Path(first_fix_path).parent), use_fixture_only=use_fixture_only)
    first_fix = load_json(first_fix_path)
    if (
        norm(first_fix.get("execution_status")) != "executed"
        or float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0) < 80.0
        or float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0) < 70.0
        or float(first_fix.get("patch_applied_rate_pct") or 0.0) < 70.0
        or float(first_fix.get("signature_advance_rate_pct") or 0.0) < 50.0
        or float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) > 10.0
    ):
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "SKIPPED",
            "execution_status": "not_executed_due_to_first_fix_gate",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_text(out_root / "summary.md", "# v0.3.31 Dual Recheck\n\n- status: `SKIPPED`\n")
        return summary

    taskset = load_json(active_taskset_path)
    tasks = _dual_rows(taskset)
    source_surface = _surface_rows_by_source(load_json(surface_index_path))
    rows: list[dict] = []
    for task in tasks:
        repair_steps = list(task.get("repair_steps") or [])
        if len(repair_steps) < 2:
            continue
        surface_row = source_surface.get(norm(task.get("source_id"))) or {}
        current_text = norm(task.get("mutated_model_text"))
        first_step = repair_steps[0]
        ranked_first = rank_medium_rhs_candidates(
            candidate_rhs_symbols=list(surface_row.get("candidate_rhs_symbols") or []),
            canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(first_step),
            canonical_package_path=norm(surface_row.get("canonical_package_path")),
            local_cluster_rhs_values=list(surface_row.get("local_cluster_rhs_values") or []),
            adjacent_component_package_paths=list(surface_row.get("adjacent_component_package_paths") or []),
        )
        first_selected = norm((ranked_first[0] or {}).get("candidate_rhs_symbol")) if ranked_first else ""
        first_repaired_text, first_patch = apply_medium_redeclare_discovery_patch(current_text=current_text, step=first_step, selected_rhs_symbol=first_selected)
        if not bool(first_patch.get("applied")):
            continue
        second_residual = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=first_repaired_text, phase="target_hit", use_fixture_only=use_fixture_only)
        retained = medium_redeclare_target_hit(second_residual)
        second_step = repair_steps[1]
        ranked_second = rank_medium_rhs_candidates(
            candidate_rhs_symbols=list(surface_row.get("candidate_rhs_symbols") or []),
            canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(second_step),
            canonical_package_path=norm(surface_row.get("canonical_package_path")),
            local_cluster_rhs_values=list(surface_row.get("local_cluster_rhs_values") or []),
            adjacent_component_package_paths=list(surface_row.get("adjacent_component_package_paths") or []),
        )
        second_selected = norm((ranked_second[0] or {}).get("candidate_rhs_symbol")) if ranked_second else ""
        second_repaired_text, second_patch = apply_medium_redeclare_discovery_patch(current_text=first_repaired_text, step=second_step, selected_rhs_symbol=second_selected)
        final_result = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=second_repaired_text, phase="resolved", use_fixture_only=use_fixture_only) if bool(second_patch.get("applied")) else {}
        rows.append(
            {
                "task_id": norm(task.get("task_id")),
                "component_subtype": norm(task.get("component_subtype")),
                "post_first_fix_target_bucket_hit": retained,
                "second_residual_medium_redeclare_retained": retained,
                "dual_full_resolution": bool(final_result.get("check_model_pass")),
            }
        )
    task_count = len(rows)
    retained_count = sum(1 for row in rows if bool(row.get("second_residual_medium_redeclare_retained")))
    resolved_count = sum(1 for row in rows if bool(row.get("dual_full_resolution")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "execution_status": "executed",
        "task_count": task_count,
        "post_first_fix_target_bucket_hit_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("post_first_fix_target_bucket_hit"))) / float(task_count), 1) if task_count else 0.0,
        "second_residual_medium_redeclare_retained_count": retained_count,
        "second_residual_medium_redeclare_retained_rate_pct": round(100.0 * retained_count / float(task_count), 1) if task_count else 0.0,
        "dual_full_resolution_rate_pct": round(100.0 * resolved_count / float(task_count), 1) if task_count else 0.0,
        "subtype_breakdown": {
            subtype: _subtype_metrics(rows, subtype)
            for subtype in (
                "boundary_like",
                "vessel_or_volume_like",
                "pipe_or_local_fluid_interface_like",
            )
        },
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.31 Dual Recheck",
                "",
                f"- status: `{summary.get('status')}`",
                f"- post_first_fix_target_bucket_hit_rate_pct: `{summary.get('post_first_fix_target_bucket_hit_rate_pct')}`",
                f"- dual_full_resolution_rate_pct: `{summary.get('dual_full_resolution_rate_pct')}`",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.31 widened medium-redeclare dual recheck.")
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--active-taskset", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"))
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0331_dual_recheck(
        first_fix_path=str(args.first_fix),
        active_taskset_path=str(args.active_taskset),
        surface_index_path=str(args.surface_index),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "execution_status": payload.get("execution_status"), "dual_full_resolution_rate_pct": payload.get("dual_full_resolution_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
