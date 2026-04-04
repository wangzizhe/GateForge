from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_25_common import (
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    build_dual_task_rows,
    build_single_task_rows,
    build_surface_index_payload,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_25_taskset import build_v0325_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_surface_export_audit"


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_v0325_surface_export_audit(
    *,
    out_dir: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR),
    surface_index_out_dir: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR),
    taskset_out_dir: str = str(DEFAULT_TASKSET_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    surface_index = build_surface_index_payload(use_fixture_only=use_fixture_only)
    single_rows = build_single_task_rows(surface_index)
    dual_rows = build_dual_task_rows(surface_index)
    total_surface_keys = int(surface_index.get("surface_export_total_count") or 0)
    export_success_count = int(surface_index.get("surface_export_success_count") or 0)
    export_success_rate_pct = float(surface_index.get("surface_export_success_rate_pct") or 0.0)
    fixture_fallback_count = int(surface_index.get("fixture_fallback_count") or 0)
    fixture_fallback_rate_pct = float(surface_index.get("fixture_fallback_rate_pct") or 0.0)
    export_failures = surface_index.get("export_failures") if isinstance(surface_index.get("export_failures"), list) else []

    surface_index_summary = {
        "schema_version": f"{SCHEMA_PREFIX}_surface_index",
        "generated_at_utc": now_utc(),
        "status": "PASS" if export_success_count else "FAIL",
        "source_mode": norm(surface_index.get("source_mode")),
        "omc_backend": norm(surface_index.get("omc_backend")),
        "docker_image": norm(surface_index.get("docker_image")),
        "modelica_version": norm(surface_index.get("modelica_version")),
        "surface_record_count": len(surface_index.get("surface_records") or {}),
        "surface_export_total_count": total_surface_keys,
        "surface_export_success_count": export_success_count,
        "surface_export_success_rate_pct": export_success_rate_pct,
        "fixture_fallback_count": fixture_fallback_count,
        "fixture_fallback_rate_pct": fixture_fallback_rate_pct,
        "export_failure_count": len(export_failures),
    }
    surface_index_payload = {
        "schema_version": f"{SCHEMA_PREFIX}_surface_index",
        "generated_at_utc": now_utc(),
        "summary": surface_index_summary,
        "surface_records": surface_index.get("surface_records") or {},
        "export_failures": export_failures,
        "source_mode": surface_index.get("source_mode"),
        "omc_backend": surface_index.get("omc_backend"),
        "docker_image": surface_index.get("docker_image"),
        "modelica_version": surface_index.get("modelica_version"),
    }
    surface_root = Path(surface_index_out_dir)
    write_json(surface_root / "summary.json", surface_index_summary)
    write_json(surface_root / "surface_index.json", surface_index_payload)
    write_text(
        surface_root / "summary.md",
        "\n".join(
            [
                "# v0.3.25 Surface Index",
                "",
                f"- status: `{surface_index_summary.get('status')}`",
                f"- surface_export_success_rate_pct: `{surface_index_summary.get('surface_export_success_rate_pct')}`",
                "",
            ]
        ),
    )

    taskset = build_v0325_taskset(
        surface_index_path=str(surface_root / "surface_index.json"),
        out_dir=taskset_out_dir,
        use_fixture_only=use_fixture_only,
    )
    taskset_summary = taskset.get("summary") if isinstance(taskset.get("summary"), dict) else {}

    if export_success_rate_pct >= 100.0 and fixture_fallback_rate_pct <= 0.0:
        execution_mode = "promoted"
        status = "PASS"
    elif export_success_rate_pct >= 80.0:
        execution_mode = "degraded_with_export_exclusions"
        status = "PASS"
    else:
        execution_mode = "blocked_surface_export"
        status = "FAIL"

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
        "single_task_count": len(single_rows),
        "active_single_task_count": int(taskset_summary.get("active_single_task_count") or 0),
        "dual_sidecar_task_count": len(dual_rows),
        "active_dual_sidecar_task_count": int(taskset_summary.get("active_dual_task_count") or 0),
        "export_excluded_count": int(taskset_summary.get("export_excluded_count") or 0),
        "export_excluded_task_ids": list(taskset_summary.get("export_excluded_task_ids") or []),
        "export_excluded_family_mix": dict(taskset_summary.get("export_excluded_family_mix") or {}),
        "active_family_mix": dict(taskset_summary.get("component_family_counts") or {}),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(
        out_root / "active_taskset.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "PASS" if status == "PASS" else "FAIL",
            "execution_mode": execution_mode,
            "single_tasks": taskset.get("single_tasks") or [],
            "dual_sidecar_tasks": taskset.get("dual_tasks") or [],
        },
    )
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.25 Surface Export Audit",
                "",
                f"- status: `{summary.get('status')}`",
                f"- execution_mode: `{summary.get('execution_mode')}`",
                f"- surface_export_success_rate_pct: `{summary.get('surface_export_success_rate_pct')}`",
                f"- export_excluded_count: `{summary.get('export_excluded_count')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "surface_index": surface_index_payload, "taskset": taskset}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.25 local-interface discovery surface export audit.")
    parser.add_argument("--out-dir", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR))
    parser.add_argument("--surface-index-out-dir", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR))
    parser.add_argument("--taskset-out-dir", default=str(DEFAULT_TASKSET_OUT_DIR))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0325_surface_export_audit(
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
