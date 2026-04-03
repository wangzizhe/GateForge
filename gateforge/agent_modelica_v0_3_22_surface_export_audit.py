from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_22_common import (
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    PARAMETER_QUERY_SPECS,
    SCHEMA_PREFIX,
    build_dual_task_rows,
    build_single_task_rows,
    build_surface_index_payload,
    now_utc,
    norm,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_surface_export_audit"


def _canonical_present(task: dict) -> bool:
    patch_type = norm(task.get("patch_type"))
    canonical = norm(task.get("correct_symbol"))
    if patch_type == "replace_class_path":
        candidates = task.get("class_path_candidates") if isinstance(task.get("class_path_candidates"), list) else []
        return canonical in [norm(item) for item in candidates]
    records = task.get("candidate_parameter_records") if isinstance(task.get("candidate_parameter_records"), list) else []
    return canonical in [norm(row.get("name")) for row in records if isinstance(row, dict)]


def _single_export_ready(task: dict) -> bool:
    return norm(task.get("candidate_provenance")) == "omc_export" and _canonical_present(task)


def _dual_export_ready(task: dict) -> bool:
    steps = task.get("repair_steps") if isinstance(task.get("repair_steps"), list) else []
    return bool(steps) and all(norm(step.get("candidate_provenance")) == "omc_export" and _canonical_present(step) for step in steps if isinstance(step, dict))


def _family_mix(rows: list[dict], key: str = "component_family") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_v0322_surface_export_audit(
    *,
    out_dir: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR),
    surface_index_out_dir: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR),
    taskset_out_dir: str = str(DEFAULT_TASKSET_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    surface_index = build_surface_index_payload(use_fixture_only=use_fixture_only)
    single_rows = build_single_task_rows(surface_index)
    dual_rows = build_dual_task_rows(surface_index)

    class_provenance = surface_index.get("class_provenance") if isinstance(surface_index.get("class_provenance"), dict) else {}
    parameter_provenance = surface_index.get("parameter_provenance") if isinstance(surface_index.get("parameter_provenance"), dict) else {}
    total_surface_keys = len(class_provenance) + len(parameter_provenance)
    export_success_count = sum(1 for value in list(class_provenance.values()) + list(parameter_provenance.values()) if norm(value) == "omc_export")
    fixture_fallback_count = total_surface_keys - export_success_count

    expected_symbol_reference_count = 0
    expected_symbol_present_count = 0
    for task in single_rows:
        expected_symbol_reference_count += 1
        if _canonical_present(task):
            expected_symbol_present_count += 1
    for task in dual_rows:
        for step in task.get("repair_steps") if isinstance(task.get("repair_steps"), list) else []:
            if not isinstance(step, dict):
                continue
            expected_symbol_reference_count += 1
            if _canonical_present(step):
                expected_symbol_present_count += 1

    inherited_reference_count = 0
    inherited_retained_count = 0
    for task in single_rows:
        if bool(task.get("requires_inherited_parameter")):
            inherited_reference_count += 1
            if _canonical_present(task):
                inherited_retained_count += 1
    for task in dual_rows:
        for step in task.get("repair_steps") if isinstance(task.get("repair_steps"), list) else []:
            if isinstance(step, dict) and bool(step.get("requires_inherited_parameter")):
                inherited_reference_count += 1
                if _canonical_present(step):
                    inherited_retained_count += 1

    active_single_tasks = [row for row in single_rows if _single_export_ready(row)]
    excluded_single_tasks = [row for row in single_rows if not _single_export_ready(row)]
    active_dual_tasks = [row for row in dual_rows if _dual_export_ready(row)]
    excluded_dual_tasks = [row for row in dual_rows if not _dual_export_ready(row)]

    export_success_rate_pct = round(100.0 * export_success_count / float(total_surface_keys), 1) if total_surface_keys else 0.0
    fixture_fallback_rate_pct = round(100.0 * fixture_fallback_count / float(total_surface_keys), 1) if total_surface_keys else 0.0
    expected_symbol_rate_pct = round(100.0 * expected_symbol_present_count / float(expected_symbol_reference_count), 1) if expected_symbol_reference_count else 0.0
    inherited_retention_rate_pct = round(100.0 * inherited_retained_count / float(inherited_reference_count), 1) if inherited_reference_count else 100.0

    if export_success_rate_pct >= 100.0 and fixture_fallback_rate_pct <= 0.0:
        execution_mode = "promoted"
        status = "PASS"
    elif export_success_rate_pct >= 80.0:
        execution_mode = "degraded_with_export_exclusions"
        status = "PASS"
    else:
        execution_mode = "blocked_surface_export"
        status = "FAIL"

    excluded_rows = excluded_single_tasks + excluded_dual_tasks
    excluded_ids = [norm(row.get("task_id")) for row in excluded_rows]
    active_taskset = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if status == "PASS" else "FAIL",
        "execution_mode": execution_mode,
        "single_tasks": active_single_tasks,
        "dual_sidecar_tasks": active_dual_tasks,
        "excluded_single_tasks": excluded_single_tasks,
        "excluded_dual_sidecar_tasks": excluded_dual_tasks,
    }

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "execution_mode": execution_mode,
        "source_mode": norm(surface_index.get("source_mode")),
        "omc_backend": norm(surface_index.get("omc_backend")),
        "docker_image": norm(surface_index.get("docker_image")),
        "modelica_version": norm(surface_index.get("modelica_version")),
        "total_surface_key_count": total_surface_keys,
        "surface_export_success_count": export_success_count,
        "surface_export_success_rate_pct": export_success_rate_pct,
        "fixture_fallback_count": fixture_fallback_count,
        "fixture_fallback_rate_pct": fixture_fallback_rate_pct,
        "surface_contains_expected_symbol_count": expected_symbol_present_count,
        "surface_contains_expected_symbol_rate_pct": expected_symbol_rate_pct,
        "inherited_parameter_reference_count": inherited_reference_count,
        "inherited_parameter_retention_count": inherited_retained_count,
        "inherited_parameter_retention_rate_pct": inherited_retention_rate_pct,
        "single_task_count": len(single_rows),
        "active_single_task_count": len(active_single_tasks),
        "dual_sidecar_task_count": len(dual_rows),
        "active_dual_sidecar_task_count": len(active_dual_tasks),
        "export_excluded_count": len(excluded_rows),
        "export_excluded_task_ids": excluded_ids,
        "export_excluded_family_mix": _family_mix(excluded_rows),
        "active_family_mix": _family_mix(active_single_tasks + active_dual_tasks),
        "parameter_surface_class_count": len(PARAMETER_QUERY_SPECS),
    }

    surface_index_summary = {
        "schema_version": f"{SCHEMA_PREFIX}_surface_index",
        "generated_at_utc": now_utc(),
        "status": "PASS" if total_surface_keys else "FAIL",
        "source_mode": norm(surface_index.get("source_mode")),
        "omc_backend": norm(surface_index.get("omc_backend")),
        "docker_image": norm(surface_index.get("docker_image")),
        "modelica_version": norm(surface_index.get("modelica_version")),
        "class_surface_key_count": len(class_provenance),
        "parameter_surface_key_count": len(parameter_provenance),
        "class_surface_total_candidate_count": sum(len(value or []) for value in (surface_index.get("class_path_candidates") or {}).values()),
        "parameter_surface_total_candidate_count": sum(len(value or []) for value in (surface_index.get("parameter_surface_records") or {}).values()),
        "fixture_fallback_count": fixture_fallback_count,
    }
    surface_index_payload = {
        "schema_version": f"{SCHEMA_PREFIX}_surface_index",
        "generated_at_utc": now_utc(),
        "summary": surface_index_summary,
        **surface_index,
    }
    full_taskset_payload = {
        "schema_version": f"{SCHEMA_PREFIX}_taskset",
        "generated_at_utc": now_utc(),
        "status": "PASS" if len(single_rows) >= 12 and len(dual_rows) >= 12 else "FAIL",
        "single_tasks": single_rows,
        "dual_sidecar_tasks": dual_rows,
    }

    surface_index_root = Path(surface_index_out_dir)
    write_json(surface_index_root / "summary.json", surface_index_summary)
    write_json(surface_index_root / "surface_index.json", surface_index_payload)
    write_text(surface_index_root / "summary.md", "\n".join(["# v0.3.22 Surface Index", "", f"- status: `{surface_index_summary.get('status')}`", f"- source_mode: `{surface_index_summary.get('source_mode')}`", ""]))

    taskset_root = Path(taskset_out_dir)
    write_json(taskset_root / "summary.json", {"schema_version": f"{SCHEMA_PREFIX}_taskset", "generated_at_utc": now_utc(), "status": full_taskset_payload.get("status"), "single_task_count": len(single_rows), "dual_sidecar_task_count": len(dual_rows)})
    write_json(taskset_root / "taskset.json", full_taskset_payload)
    write_text(taskset_root / "summary.md", "\n".join(["# v0.3.22 Taskset", "", f"- status: `{full_taskset_payload.get('status')}`", f"- single_task_count: `{len(single_rows)}`", f"- dual_sidecar_task_count: `{len(dual_rows)}`", ""]))

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "active_taskset.json", active_taskset)
    write_json(
        out_root / "failure_taxonomy.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": status,
            "class_provenance": class_provenance,
            "parameter_provenance": parameter_provenance,
            "excluded_task_ids": excluded_ids,
        },
    )
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.22 Surface Export Audit",
                "",
                f"- status: `{summary.get('status')}`",
                f"- execution_mode: `{summary.get('execution_mode')}`",
                f"- surface_export_success_rate_pct: `{summary.get('surface_export_success_rate_pct')}`",
                f"- fixture_fallback_rate_pct: `{summary.get('fixture_fallback_rate_pct')}`",
                f"- export_excluded_count: `{summary.get('export_excluded_count')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "active_taskset": active_taskset, "surface_index": surface_index_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.22 surface export coverage audit.")
    parser.add_argument("--out-dir", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR))
    parser.add_argument("--surface-index-out-dir", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR))
    parser.add_argument("--taskset-out-dir", default=str(DEFAULT_TASKSET_OUT_DIR))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0322_surface_export_audit(
        out_dir=str(args.out_dir),
        surface_index_out_dir=str(args.surface_index_out_dir),
        taskset_out_dir=str(args.taskset_out_dir),
        use_fixture_only=bool(args.fixture_only),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "surface_export_success_rate_pct": summary.get("surface_export_success_rate_pct"), "export_excluded_count": summary.get("export_excluded_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
