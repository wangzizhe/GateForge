from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_31_common import (
    DEFAULT_MANIFEST_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    build_medium_candidate_rhs_symbols,
    load_json,
    norm,
    now_utc,
    parse_canonical_rhs_from_repair_step,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_31_coverage_manifest import build_v0331_coverage_manifest


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_surface_export_audit"


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _dual_rows(payload: dict) -> list[dict]:
    rows = payload.get("dual_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_v0331_surface_export_audit(
    *,
    manifest_path: str = str(DEFAULT_MANIFEST_OUT_DIR / "taskset.json"),
    out_dir: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(manifest_path).exists():
        build_v0331_coverage_manifest(out_dir=str(Path(manifest_path).parent), use_fixture_only=use_fixture_only)
    manifest = load_json(manifest_path)
    manifest_summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    if not bool(manifest_summary.get("handoff_substrate_valid")):
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "execution_mode": "handoff_substrate_invalid",
            "surface_export_success_rate_pct": 0.0,
            "canonical_in_candidate_rate_pct": 0.0,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_json(out_root / "surface_index.json", {"summary": summary, "task_rows": []})
        write_json(out_root / "active_taskset.json", {"summary": summary, "single_tasks": [], "dual_tasks": []})
        return {"summary": summary}

    single_rows = _single_rows(manifest)
    dual_rows = _dual_rows(manifest)
    surface_rows: list[dict] = []
    source_pass: dict[str, bool] = {}
    for task in single_rows:
        step = ((task.get("repair_steps") or [{}])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        candidate_info = build_medium_candidate_rhs_symbols(
            source_model_text=norm(task.get("source_model_text")),
            canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(step),
            use_fixture_only=use_fixture_only,
        )
        candidate_symbols = [norm(x) for x in (candidate_info.get("candidate_rhs_symbols") or []) if norm(x)]
        canonical_symbol = norm(candidate_info.get("canonical_rhs_symbol"))
        source_export_ok = bool(candidate_symbols)
        canonical_in_candidate = canonical_symbol in candidate_symbols
        row = {
            "task_id": norm(task.get("task_id")),
            "source_id": norm(task.get("source_id")),
            "component_name": norm(task.get("component_name")),
            "component_subtype": norm(task.get("component_subtype")),
            "canonical_rhs_symbol": canonical_symbol,
            "canonical_package_path": norm(candidate_info.get("canonical_package_path")),
            "candidate_rhs_symbols": candidate_symbols,
            "local_cluster_rhs_values": list(candidate_info.get("local_cluster_rhs_values") or []),
            "adjacent_component_package_paths": list(candidate_info.get("adjacent_component_package_paths") or []),
            "source_export_ok": source_export_ok,
            "canonical_in_candidate": canonical_in_candidate,
        }
        surface_rows.append(row)
        source_id = norm(task.get("source_id"))
        source_pass[source_id] = source_pass.get(source_id, True) and source_export_ok and canonical_in_candidate

    task_count = len(surface_rows)
    export_ok_count = sum(1 for row in surface_rows if bool(row.get("source_export_ok")))
    canonical_ok_count = sum(1 for row in surface_rows if bool(row.get("canonical_in_candidate")))
    export_excluded_rows = [row for row in surface_rows if not bool(row.get("source_export_ok"))]
    canonical_excluded_rows = [row for row in surface_rows if bool(row.get("source_export_ok")) and not bool(row.get("canonical_in_candidate"))]
    active_single = [
        task
        for task in single_rows
        if norm(task.get("task_id")) not in {norm(row.get("task_id")) for row in export_excluded_rows + canonical_excluded_rows}
    ]
    active_dual = [task for task in dual_rows if bool(source_pass.get(norm(task.get("source_id")), False))]
    if task_count and export_ok_count == task_count and canonical_ok_count == task_count:
        execution_mode = "promoted"
        status = "PASS"
    elif task_count and (100.0 * export_ok_count / float(task_count)) >= 80.0 and (100.0 * canonical_ok_count / float(task_count)) >= 80.0:
        execution_mode = "degraded_with_substrate_exclusions"
        status = "PASS"
    else:
        execution_mode = "blocked_surface_export"
        status = "FAIL"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "execution_mode": execution_mode,
        "surface_export_success_rate_pct": round(100.0 * export_ok_count / float(task_count), 1) if task_count else 0.0,
        "canonical_in_candidate_rate_pct": round(100.0 * canonical_ok_count / float(task_count), 1) if task_count else 0.0,
        "fixture_fallback_rate_pct": 0.0,
        "active_single_task_count": len(active_single),
        "active_dual_task_count": len(active_dual),
        "coverage_construction_mode": norm(manifest_summary.get("coverage_construction_mode")),
        "export_excluded_count": len(export_excluded_rows),
        "export_excluded_task_ids": [norm(row.get("task_id")) for row in export_excluded_rows],
        "export_excluded_subtype_counts": _count_by(export_excluded_rows, "component_subtype"),
        "canonical_miss_excluded_count": len(canonical_excluded_rows),
        "canonical_miss_excluded_task_ids": [norm(row.get("task_id")) for row in canonical_excluded_rows],
        "canonical_miss_excluded_subtype_counts": _count_by(canonical_excluded_rows, "component_subtype"),
        "active_subtype_counts": _count_by(active_single, "component_subtype"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "surface_index.json", {"summary": summary, "task_rows": surface_rows})
    write_json(
        out_root / "active_taskset.json",
        {
            "summary": summary,
            "single_tasks": active_single,
            "dual_tasks": active_dual,
        },
    )
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.31 Surface Export Audit",
                "",
                f"- status: `{summary.get('status')}`",
                f"- execution_mode: `{summary.get('execution_mode')}`",
                f"- surface_export_success_rate_pct: `{summary.get('surface_export_success_rate_pct')}`",
                f"- canonical_in_candidate_rate_pct: `{summary.get('canonical_in_candidate_rate_pct')}`",
            ]
        ),
    )
    return {"summary": summary, "task_rows": surface_rows, "active_single": active_single, "active_dual": active_dual}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.31 widened medium-redeclare surface export audit.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_OUT_DIR / "taskset.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0331_surface_export_audit(
        manifest_path=str(args.manifest),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "execution_mode": summary.get("execution_mode"), "active_dual_task_count": summary.get("active_dual_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
