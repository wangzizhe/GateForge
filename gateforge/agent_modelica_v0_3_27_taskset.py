from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_27_common import (
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    DEFAULT_TASKSET_PRECHECK_RESULTS_DIR,
    DUAL_RECHECK_SPECS,
    SCHEMA_PREFIX,
    SINGLE_MISMATCH_SPECS,
    build_dual_task_rows,
    build_single_task_rows,
    build_surface_index_payload,
    build_v0327_source_specs,
    dry_run_dual_task,
    dry_run_single_task,
    fixture_dry_run_result,
    load_json,
    norm,
    now_utc,
    precheck_neighbor_dual_second_residual,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_taskset"


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_v0327_taskset(
    *,
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"),
    out_dir: str = str(DEFAULT_TASKSET_OUT_DIR),
    precheck_results_dir: str = str(DEFAULT_TASKSET_PRECHECK_RESULTS_DIR),
    use_fixture_only: bool = False,
) -> dict:
    target_surface_index = Path(surface_index_path)
    if use_fixture_only or not target_surface_index.exists():
        payload = build_surface_index_payload(use_fixture_only=use_fixture_only)
        records = payload.get("surface_records") if isinstance(payload.get("surface_records"), dict) else {}
        export_failures = payload.get("export_failures") if isinstance(payload.get("export_failures"), list) else []
        summary = {
            "schema_version": f"{SCHEMA_PREFIX}_surface_index",
            "generated_at_utc": now_utc(),
            "status": "PASS" if records else "FAIL",
            "source_mode": payload.get("source_mode"),
            "omc_backend": payload.get("omc_backend"),
            "docker_image": payload.get("docker_image"),
            "modelica_version": payload.get("modelica_version"),
            "surface_record_count": len(records),
            "surface_export_total_count": int(payload.get("surface_export_total_count") or 0),
            "surface_export_success_count": int(payload.get("surface_export_success_count") or 0),
            "surface_export_success_rate_pct": float(payload.get("surface_export_success_rate_pct") or 0.0),
            "fixture_fallback_rate_pct": float(payload.get("fixture_fallback_rate_pct") or 0.0),
            "export_failure_count": len(export_failures),
        }
        write_json(target_surface_index.parent / "summary.json", summary)
        write_json(
            target_surface_index,
            {
                "schema_version": f"{SCHEMA_PREFIX}_surface_index",
                "generated_at_utc": now_utc(),
                "summary": summary,
                "surface_records": records,
                "export_failures": export_failures,
                "source_mode": payload.get("source_mode"),
                "omc_backend": payload.get("omc_backend"),
                "docker_image": payload.get("docker_image"),
                "modelica_version": payload.get("modelica_version"),
            },
        )
    surface_index_payload = load_json(surface_index_path)
    single_candidates = build_single_task_rows(surface_index_payload)
    dual_candidates = build_dual_task_rows(surface_index_payload)
    export_failures = []
    single_rows: list[dict] = []
    dual_rows: list[dict] = []
    for task in single_candidates:
        if not list(task.get("candidate_symbols") or []):
            export_failures.append({"task_id": norm(task.get("task_id")), "component_family": norm(task.get("component_family")), "reason": "empty_candidate_surface"})
            continue
        if not bool(task.get("canonical_absent_elsewhere_from_source_model")):
            export_failures.append({"task_id": norm(task.get("task_id")), "component_family": norm(task.get("component_family")), "reason": "canonical_endpoint_present_elsewhere_in_source_model"})
            continue
        row = dict(task)
        row["spec_time_dry_run"] = fixture_dry_run_result() if use_fixture_only else dry_run_single_task(task)
        single_rows.append(row)
    for task in dual_candidates:
        if any(not list(step.get("candidate_symbols") or []) for step in task.get("repair_steps") or []):
            export_failures.append({"task_id": norm(task.get("task_id")), "component_family": norm(task.get("component_family")), "reason": "empty_candidate_surface"})
            continue
        if not bool(task.get("canonical_absent_elsewhere_from_source_model")):
            export_failures.append({"task_id": norm(task.get("task_id")), "component_family": norm(task.get("component_family")), "reason": "canonical_endpoint_present_elsewhere_in_source_model"})
            continue
        row = dict(task)
        row["spec_time_dry_run"] = fixture_dry_run_result() if use_fixture_only else dry_run_dual_task(task)
        row["post_first_fix_precheck"] = precheck_neighbor_dual_second_residual(
            task=row,
            results_dir=precheck_results_dir,
            timeout_sec=600,
            use_fixture_only=use_fixture_only,
        )
        dual_rows.append(row)
    active_single = [row for row in single_rows if bool((row.get("spec_time_dry_run") or {}).get("target_bucket_hit"))]
    active_dual = [
        row
        for row in dual_rows
        if bool((row.get("spec_time_dry_run") or {}).get("target_bucket_hit"))
        and bool((row.get("post_first_fix_precheck") or {}).get("second_residual_target_bucket_hit"))
    ]
    total_candidate_count = len(single_candidates) + len(dual_candidates)
    admitted_candidate_count = len(single_rows) + len(dual_rows)
    export_success_rate = round(100.0 * admitted_candidate_count / float(total_candidate_count), 1) if total_candidate_count else 0.0
    execution_mode = "promoted" if export_success_rate >= 100.0 else ("degraded" if export_success_rate >= 80.0 else "blocked")
    dual_precheck_hit_count = sum(1 for row in dual_rows if bool((row.get("post_first_fix_precheck") or {}).get("second_residual_target_bucket_hit")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if execution_mode in {"promoted", "degraded"} and len(active_single) >= 12 and len(active_dual) >= 10 else "FAIL",
        "execution_mode": execution_mode,
        "source_count": len(build_v0327_source_specs()),
        "source_tier_counts": _count_by(build_v0327_source_specs(), "complexity_tier"),
        "single_task_count": len(single_candidates),
        "dual_sidecar_task_count": len(dual_candidates),
        "active_single_task_count": len(active_single),
        "active_dual_task_count": len(active_dual),
        "single_target_bucket_hit_rate_pct": round(100.0 * len(active_single) / float(len(single_rows)), 1) if single_rows else 0.0,
        "dual_target_bucket_hit_rate_pct": round(100.0 * sum(1 for row in dual_rows if bool((row.get("spec_time_dry_run") or {}).get("target_bucket_hit"))) / float(len(dual_rows)), 1) if dual_rows else 0.0,
        "neighbor_post_first_fix_target_bucket_hit_count": dual_precheck_hit_count,
        "neighbor_post_first_fix_target_bucket_hit_rate_pct": round(100.0 * dual_precheck_hit_count / float(len(dual_rows)), 1) if dual_rows else 0.0,
        "surface_export_success_rate_pct": export_success_rate,
        "fixture_fallback_rate_pct": 0.0,
        "export_excluded_count": len(export_failures),
        "export_excluded_task_ids": [norm(row.get("task_id")) for row in export_failures],
        "export_excluded_family_mix": _count_by(export_failures, "component_family"),
        "export_exclusion_reason_counts": _count_by(export_failures, "reason"),
        "component_family_counts": _count_by(active_single + active_dual, "component_family"),
        "placement_kind_counts": _count_by(active_dual, "placement_kind"),
        "frozen_single_task_ids": [norm(row.get("task_id")) for row in active_single],
        "frozen_dual_task_ids": [norm(row.get("task_id")) for row in active_dual],
        "surface_record_count": len(surface_index_payload.get("surface_records") or {}),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "single_tasks": active_single,
        "dual_tasks": active_dual,
        "single_candidates": single_rows,
        "dual_candidates": dual_rows,
        "export_failures": export_failures,
        "pattern_family_counts": {
            "single_component_families": _count_by([dict(row) for row in SINGLE_MISMATCH_SPECS], "component_family"),
            "dual_component_families": _count_by([dict(row) for row in DUAL_RECHECK_SPECS], "component_family"),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "taskset.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.27 Taskset",
                "",
                f"- status: `{summary.get('status')}`",
                f"- execution_mode: `{summary.get('execution_mode')}`",
                f"- active_single_task_count: `{summary.get('active_single_task_count')}`",
                f"- active_dual_task_count: `{summary.get('active_dual_task_count')}`",
                f"- neighbor_post_first_fix_target_bucket_hit_rate_pct: `{summary.get('neighbor_post_first_fix_target_bucket_hit_rate_pct')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.27 neighbor-component local-interface discovery taskset.")
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_TASKSET_OUT_DIR))
    parser.add_argument("--precheck-results-dir", default=str(DEFAULT_TASKSET_PRECHECK_RESULTS_DIR))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0327_taskset(
        surface_index_path=str(args.surface_index),
        out_dir=str(args.out_dir),
        precheck_results_dir=str(args.precheck_results_dir),
        use_fixture_only=bool(args.fixture_only),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "execution_mode": summary.get("execution_mode"), "active_single_task_count": summary.get("active_single_task_count"), "active_dual_task_count": summary.get("active_dual_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
