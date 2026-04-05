from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_33_common import (
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    apply_pipe_slice_discovery_patch,
    dual_context_metrics,
    norm,
    now_utc,
    parse_canonical_rhs_from_repair_step,
    pipe_slice_target_hit,
    probe_resolved_result,
    probe_target_result,
    rank_medium_rhs_candidates,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_33_first_fix_evidence import build_v0333_first_fix_evidence


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dual_recheck"


def _surface_rows_by_source(payload: dict) -> dict[str, list[dict]]:
    rows = payload.get("task_rows")
    mapping: dict[str, list[dict]] = {}
    if not isinstance(rows, list):
        return mapping
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_id = norm(row.get("source_id"))
        if not source_id:
            continue
        mapping.setdefault(source_id, []).append(row)
    return mapping


def _dual_rows(payload: dict) -> list[dict]:
    rows = payload.get("dual_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_v0333_dual_recheck(
    *,
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    active_taskset_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"),
    surface_index_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"),
    out_dir: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(first_fix_path).exists():
        build_v0333_first_fix_evidence(out_dir=str(Path(first_fix_path).parent), use_fixture_only=use_fixture_only)
    first_fix = json.loads(Path(first_fix_path).read_text(encoding="utf-8"))
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
        write_text(out_root / "summary.md", "# v0.3.33 Dual Recheck\n\n- status: `SKIPPED`\n")
        return summary

    taskset = json.loads(Path(active_taskset_path).read_text(encoding="utf-8"))
    tasks = _dual_rows(taskset)
    surface_by_source = _surface_rows_by_source(json.loads(Path(surface_index_path).read_text(encoding="utf-8")))
    rows: list[dict] = []
    for task in tasks:
        repair_steps = list(task.get("repair_steps") or [])
        if len(repair_steps) < 2:
            continue
        source_rows = surface_by_source.get(norm(task.get("source_id"))) or []
        candidate_rhs_symbols = []
        local_cluster_rhs_values = []
        adjacent_component_package_paths = []
        canonical_package_path = ""
        for row in source_rows:
            for value in list(row.get("candidate_rhs_symbols") or []):
                if norm(value) and norm(value) not in candidate_rhs_symbols:
                    candidate_rhs_symbols.append(norm(value))
            for value in list(row.get("local_cluster_rhs_values") or []):
                if norm(value) and norm(value) not in local_cluster_rhs_values:
                    local_cluster_rhs_values.append(norm(value))
            for value in list(row.get("adjacent_component_package_paths") or []):
                if norm(value) and norm(value) not in adjacent_component_package_paths:
                    adjacent_component_package_paths.append(norm(value))
            if not canonical_package_path and norm(row.get("canonical_package_path")):
                canonical_package_path = norm(row.get("canonical_package_path"))

        current_text = norm(task.get("mutated_model_text"))
        first_step = repair_steps[0]
        ranked_first = rank_medium_rhs_candidates(
            candidate_rhs_symbols=candidate_rhs_symbols,
            canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(first_step),
            canonical_package_path=canonical_package_path,
            local_cluster_rhs_values=local_cluster_rhs_values,
            adjacent_component_package_paths=adjacent_component_package_paths,
        )
        first_selected = norm((ranked_first[0] or {}).get("candidate_rhs_symbol")) if ranked_first else ""
        first_repaired_text, first_patch = apply_pipe_slice_discovery_patch(
            current_text=current_text,
            step=first_step,
            selected_rhs_symbol=first_selected,
        )
        if not bool(first_patch.get("applied")):
            continue
        second_residual = probe_target_result(
            model_name=norm(task.get("model_name")),
            model_text=first_repaired_text,
            wrong_symbol="MediumPort",
            use_fixture_only=use_fixture_only,
        )
        second_step = repair_steps[1]
        ranked_second = rank_medium_rhs_candidates(
            candidate_rhs_symbols=candidate_rhs_symbols,
            canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(second_step),
            canonical_package_path=canonical_package_path,
            local_cluster_rhs_values=local_cluster_rhs_values,
            adjacent_component_package_paths=adjacent_component_package_paths,
        )
        second_selected = norm((ranked_second[0] or {}).get("candidate_rhs_symbol")) if ranked_second else ""
        second_repaired_text, second_patch = apply_pipe_slice_discovery_patch(
            current_text=first_repaired_text,
            step=second_step,
            selected_rhs_symbol=second_selected,
        )
        final_result = probe_resolved_result(
            model_name=norm(task.get("model_name")),
            model_text=second_repaired_text,
            use_fixture_only=use_fixture_only,
        ) if bool(second_patch.get("applied")) else {}
        second_retained = pipe_slice_target_hit(second_residual)
        rows.append(
            {
                "task_id": norm(task.get("task_id")),
                "pipe_slice_context": norm(task.get("pipe_slice_context")),
                "pipe_slice_second_residual": second_retained,
                "pipe_slice_second_residual_medium_redeclare_retained": second_retained,
                "pipe_slice_dual_full_resolution": bool(final_result.get("check_model_pass")),
            }
        )
    task_count = len(rows)
    retained_count = sum(1 for row in rows if bool(row.get("pipe_slice_second_residual_medium_redeclare_retained")))
    resolved_count = sum(1 for row in rows if bool(row.get("pipe_slice_dual_full_resolution")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "execution_status": "executed",
        "task_count": task_count,
        "pipe_slice_second_residual_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("pipe_slice_second_residual"))) / float(task_count), 1) if task_count else 0.0,
        "pipe_slice_second_residual_medium_redeclare_retained_count": retained_count,
        "pipe_slice_second_residual_medium_redeclare_retained_rate_pct": round(100.0 * retained_count / float(task_count), 1) if task_count else 0.0,
        "pipe_slice_dual_full_resolution_rate_pct": round(100.0 * resolved_count / float(task_count), 1) if task_count else 0.0,
        "subtype_breakdown": {
            context: dual_context_metrics(rows, context)
            for context in ("pipe_component_like", "fluid_port_like", "mixed_pipe_port_like")
        },
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.33 Dual Recheck",
                "",
                f"- status: `{summary.get('status')}`",
                f"- pipe_slice_second_residual_rate_pct: `{summary.get('pipe_slice_second_residual_rate_pct')}`",
                f"- pipe_slice_dual_full_resolution_rate_pct: `{summary.get('pipe_slice_dual_full_resolution_rate_pct')}`",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.33 widened pipe-slice dual recheck.")
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--active-taskset", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"))
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0333_dual_recheck(
        first_fix_path=str(args.first_fix),
        active_taskset_path=str(args.active_taskset),
        surface_index_path=str(args.surface_index),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "execution_status": payload.get("execution_status"), "pipe_slice_dual_full_resolution_rate_pct": payload.get("pipe_slice_dual_full_resolution_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
