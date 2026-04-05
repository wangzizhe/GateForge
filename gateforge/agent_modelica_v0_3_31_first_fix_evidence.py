from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_31_common import (
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
from .agent_modelica_v0_3_31_surface_export_audit import build_v0331_surface_export_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def _surface_row_map(payload: dict) -> dict[str, dict]:
    rows = payload.get("task_rows")
    return {norm(row.get("task_id")): row for row in rows if isinstance(row, dict) and norm(row.get("task_id"))} if isinstance(rows, list) else {}


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
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
        "candidate_contains_canonical_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("candidate_contains_canonical"))) / float(count), 1),
        "candidate_top1_canonical_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("candidate_top1_is_canonical"))) / float(count), 1),
        "patch_applied_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("patch_applied"))) / float(count), 1),
        "signature_advance_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("signature_advance"))) / float(count), 1),
        "drift_to_compile_failure_unknown_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("drift_to_compile_failure_unknown"))) / float(count), 1),
    }


def build_v0331_first_fix_evidence(
    *,
    surface_audit_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"),
    active_taskset_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"),
    surface_index_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"),
    out_dir: str = str(DEFAULT_FIRST_FIX_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(surface_audit_path).exists() or not Path(active_taskset_path).exists() or not Path(surface_index_path).exists():
        build_v0331_surface_export_audit(out_dir=str(Path(surface_audit_path).parent), use_fixture_only=use_fixture_only)
    surface_summary = load_json(surface_audit_path)
    if norm(surface_summary.get("status")) != "PASS":
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "SKIPPED",
            "execution_status": "not_executed_due_to_surface_export_gate",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_text(out_root / "summary.md", "# v0.3.31 First-Fix Evidence\n\n- status: `SKIPPED`\n")
        return summary

    taskset = load_json(active_taskset_path)
    tasks = _single_rows(taskset)
    surface_rows = _surface_row_map(load_json(surface_index_path))
    rows: list[dict] = []
    reason_counts: dict[str, int] = {}
    source_failure_counts: dict[str, int] = {}
    ranking_failure_counts: dict[str, int] = {}
    drift_reason_counts: dict[str, int] = {}
    drift_task_ids: list[str] = []
    for task in tasks:
        task_id = norm(task.get("task_id"))
        surface_row = surface_rows.get(task_id) or {}
        step = ((task.get("repair_steps") or [{}])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        initial = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=norm(task.get("mutated_model_text")), phase="target_hit", use_fixture_only=use_fixture_only)
        ranked = rank_medium_rhs_candidates(
            candidate_rhs_symbols=list(surface_row.get("candidate_rhs_symbols") or []),
            canonical_rhs_symbol=norm(surface_row.get("canonical_rhs_symbol")),
            canonical_package_path=norm(surface_row.get("canonical_package_path")),
            local_cluster_rhs_values=list(surface_row.get("local_cluster_rhs_values") or []),
            adjacent_component_package_paths=list(surface_row.get("adjacent_component_package_paths") or []),
        )
        selected_rhs_symbol = norm((ranked[0] or {}).get("candidate_rhs_symbol")) if ranked else ""
        canonical_rhs_symbol = parse_canonical_rhs_from_repair_step(step)
        patched_text, patch_meta = apply_medium_redeclare_discovery_patch(
            current_text=norm(task.get("mutated_model_text")),
            step=step,
            selected_rhs_symbol=selected_rhs_symbol,
        )
        post = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=patched_text, phase="resolved", use_fixture_only=use_fixture_only) if bool(patch_meta.get("applied")) else {}
        signature_advance = bool(post.get("check_model_pass") or (norm(initial.get("error_signature")) != norm(post.get("error_signature"))))
        candidate_contains_canonical = canonical_rhs_symbol in [norm(x) for x in (surface_row.get("candidate_rhs_symbols") or [])]
        candidate_top1_is_canonical = selected_rhs_symbol == canonical_rhs_symbol
        drift = bool(not post.get("check_model_pass") and norm(post.get("error_subtype")) == "compile_failure_unknown" and not medium_redeclare_target_hit(post))
        if drift:
            drift_task_ids.append(task_id)
            drift_reason = "drift_to_compile_failure_unknown"
            drift_reason_counts[drift_reason] = drift_reason_counts.get(drift_reason, 0) + 1
        if not signature_advance:
            if not candidate_contains_canonical:
                source_failure_counts["candidate_source_missing_canonical"] = source_failure_counts.get("candidate_source_missing_canonical", 0) + 1
                reason = "candidate_source_missing_canonical"
            elif not candidate_top1_is_canonical:
                ranking_failure_counts["wrong_candidate_selected"] = ranking_failure_counts.get("wrong_candidate_selected", 0) + 1
                reason = "wrong_candidate_selected"
            elif not bool(patch_meta.get("applied")):
                reason = "no_patch_applied"
            else:
                reason = "patch_missed_focal_token"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        rows.append(
            {
                "task_id": task_id,
                "component_subtype": norm(task.get("component_subtype")),
                "target_first_failure_hit": medium_redeclare_target_hit(initial),
                "candidate_contains_canonical": candidate_contains_canonical,
                "candidate_top1_is_canonical": candidate_top1_is_canonical,
                "patch_applied": bool(patch_meta.get("applied")),
                "signature_advance": signature_advance,
                "drift_to_compile_failure_unknown": drift,
                "selected_rhs_symbol": selected_rhs_symbol,
                "canonical_rhs_symbol": canonical_rhs_symbol,
            }
        )
    task_count = len(rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "execution_status": "executed",
        "task_count": task_count,
        "target_first_failure_hit_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("target_first_failure_hit"))) / float(task_count), 1) if task_count else 0.0,
        "candidate_contains_canonical_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("candidate_contains_canonical"))) / float(task_count), 1) if task_count else 0.0,
        "candidate_top1_canonical_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("candidate_top1_is_canonical"))) / float(task_count), 1) if task_count else 0.0,
        "patch_applied_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("patch_applied"))) / float(task_count), 1) if task_count else 0.0,
        "signature_advance_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("signature_advance"))) / float(task_count), 1) if task_count else 0.0,
        "drift_to_compile_failure_unknown_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("drift_to_compile_failure_unknown"))) / float(task_count), 1) if task_count else 0.0,
        "candidate_source_failure_counts": source_failure_counts,
        "candidate_ranking_failure_counts": ranking_failure_counts,
        "signature_advance_not_fired_reason_counts": reason_counts,
        "drift_task_count": len(drift_task_ids),
        "drift_task_ids": drift_task_ids,
        "drift_reason_counts": drift_reason_counts,
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
                "# v0.3.31 First-Fix Evidence",
                "",
                f"- status: `{summary.get('status')}`",
                f"- candidate_contains_canonical_rate_pct: `{summary.get('candidate_contains_canonical_rate_pct')}`",
                f"- candidate_top1_canonical_rate_pct: `{summary.get('candidate_top1_canonical_rate_pct')}`",
                f"- signature_advance_rate_pct: `{summary.get('signature_advance_rate_pct')}`",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.31 widened medium-redeclare first-fix/discovery evidence.")
    parser.add_argument("--surface-audit", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--active-taskset", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"))
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0331_first_fix_evidence(
        surface_audit_path=str(args.surface_audit),
        active_taskset_path=str(args.active_taskset),
        surface_index_path=str(args.surface_index),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "execution_status": payload.get("execution_status"), "candidate_top1_canonical_rate_pct": payload.get("candidate_top1_canonical_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
