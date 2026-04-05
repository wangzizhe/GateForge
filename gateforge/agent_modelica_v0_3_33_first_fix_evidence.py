from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_33_common import (
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    apply_pipe_slice_discovery_patch,
    build_medium_candidate_rhs_symbols,
    first_fix_subtype_metrics,
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
from .agent_modelica_v0_3_33_surface_export_audit import build_v0333_surface_export_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def _surface_row_map(payload: dict) -> dict[str, dict]:
    rows = payload.get("task_rows")
    return {norm(row.get("task_id")): row for row in rows if isinstance(row, dict) and norm(row.get("task_id"))} if isinstance(rows, list) else {}


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_v0333_first_fix_evidence(
    *,
    surface_audit_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"),
    active_taskset_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"),
    surface_index_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"),
    out_dir: str = str(DEFAULT_FIRST_FIX_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(surface_audit_path).exists() or not Path(active_taskset_path).exists() or not Path(surface_index_path).exists():
        build_v0333_surface_export_audit(out_dir=str(Path(surface_audit_path).parent), use_fixture_only=use_fixture_only)
    surface_summary = json.loads(Path(surface_audit_path).read_text(encoding="utf-8"))
    if (
        norm(surface_summary.get("status")) != "PASS"
        or float(surface_summary.get("surface_export_success_rate_pct") or 0.0) < 80.0
        or float(surface_summary.get("canonical_in_candidate_rate_pct") or 0.0) < 80.0
    ):
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "SKIPPED",
            "execution_status": "not_executed_due_to_surface_export_gate",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_text(out_root / "summary.md", "# v0.3.33 First-Fix Evidence\n\n- status: `SKIPPED`\n")
        return summary

    taskset = json.loads(Path(active_taskset_path).read_text(encoding="utf-8"))
    tasks = _single_rows(taskset)
    surface_rows = _surface_row_map(json.loads(Path(surface_index_path).read_text(encoding="utf-8")))
    rows: list[dict] = []
    source_failure_counts: dict[str, int] = {}
    ranking_failure_counts: dict[str, int] = {}
    signature_reason_counts: dict[str, int] = {}
    drift_reason_counts: dict[str, int] = {}
    drift_task_ids: list[str] = []
    for task in tasks:
        task_id = norm(task.get("task_id"))
        surface_row = surface_rows.get(task_id) or {}
        step = ((task.get("repair_steps") or [])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        candidate_info = build_medium_candidate_rhs_symbols(
            source_model_text=norm(task.get("source_model_text")),
            canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(step),
            use_fixture_only=use_fixture_only,
        )
        ranked = rank_medium_rhs_candidates(
            candidate_rhs_symbols=list(candidate_info.get("candidate_rhs_symbols") or []),
            canonical_rhs_symbol=norm(candidate_info.get("canonical_rhs_symbol")),
            canonical_package_path=norm(candidate_info.get("canonical_package_path")),
            local_cluster_rhs_values=list(candidate_info.get("local_cluster_rhs_values") or []),
            adjacent_component_package_paths=list(candidate_info.get("adjacent_component_package_paths") or []),
        )
        selected_rhs_symbol = norm((ranked[0] or {}).get("candidate_rhs_symbol")) if ranked else ""
        canonical_rhs_symbol = parse_canonical_rhs_from_repair_step(step)
        initial = probe_target_result(
            model_name=norm(task.get("model_name")),
            model_text=norm(task.get("mutated_model_text")),
            wrong_symbol=norm(task.get("wrong_symbol")),
            use_fixture_only=use_fixture_only,
        )
        patched_text, patch_meta = apply_pipe_slice_discovery_patch(
            current_text=norm(task.get("mutated_model_text")),
            step=step,
            selected_rhs_symbol=selected_rhs_symbol,
        )
        post = probe_resolved_result(
            model_name=norm(task.get("model_name")),
            model_text=patched_text,
            use_fixture_only=use_fixture_only,
        ) if bool(patch_meta.get("applied")) else {}
        candidate_contains_canonical = canonical_rhs_symbol in [norm(x) for x in (surface_row.get("candidate_rhs_symbols") or candidate_info.get("candidate_rhs_symbols") or [])]
        candidate_top1_is_canonical = selected_rhs_symbol == canonical_rhs_symbol
        signature_advance = bool(post.get("check_model_pass") or (norm(initial.get("error_signature")) != norm(post.get("error_signature"))))
        drift = bool(not post.get("check_model_pass") and norm(post.get("error_subtype")) == "compile_failure_unknown" and not pipe_slice_target_hit(post))
        if drift:
            drift_task_ids.append(task_id)
            drift_reason_counts["drift_to_compile_failure_unknown"] = drift_reason_counts.get("drift_to_compile_failure_unknown", 0) + 1
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
            signature_reason_counts[reason] = signature_reason_counts.get(reason, 0) + 1
        rows.append(
            {
                "task_id": task_id,
                "pipe_slice_context": norm(task.get("pipe_slice_context")),
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
        "candidate_contains_canonical_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("candidate_contains_canonical"))) / float(task_count), 1) if task_count else 0.0,
        "candidate_top1_canonical_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("candidate_top1_is_canonical"))) / float(task_count), 1) if task_count else 0.0,
        "patch_applied_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("patch_applied"))) / float(task_count), 1) if task_count else 0.0,
        "signature_advance_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("signature_advance"))) / float(task_count), 1) if task_count else 0.0,
        "drift_to_compile_failure_unknown_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("drift_to_compile_failure_unknown"))) / float(task_count), 1) if task_count else 0.0,
        "candidate_source_failure_counts": source_failure_counts,
        "candidate_ranking_failure_counts": ranking_failure_counts,
        "signature_advance_not_fired_reason_counts": signature_reason_counts,
        "drift_task_count": len(drift_task_ids),
        "drift_task_ids": drift_task_ids,
        "drift_reason_counts": drift_reason_counts,
        "subtype_breakdown": {
            context: first_fix_subtype_metrics(rows, context)
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
                "# v0.3.33 First-Fix Evidence",
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
    parser = argparse.ArgumentParser(description="Build the v0.3.33 widened pipe-slice first-fix/discovery evidence.")
    parser.add_argument("--surface-audit", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--active-taskset", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json"))
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "surface_index.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0333_first_fix_evidence(
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
