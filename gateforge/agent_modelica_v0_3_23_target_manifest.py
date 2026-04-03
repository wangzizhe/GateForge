from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_23_common import (
    DEFAULT_TARGET_MANIFEST_OUT_DIR,
    DUAL_RECHECK_SPECS,
    SCHEMA_PREFIX,
    SINGLE_MISMATCH_SPECS,
    build_single_task_rows,
    build_v0323_source_specs,
    build_dual_task_rows,
    dry_run_dual_task,
    dry_run_single_task,
    fixture_dry_run_result,
    now_utc,
    norm,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_target_manifest"


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_v0323_target_manifest(*, out_dir: str = str(DEFAULT_TARGET_MANIFEST_OUT_DIR), use_fixture_only: bool = False) -> dict:
    sources = build_v0323_source_specs()
    single_tasks = build_single_task_rows()
    dual_tasks = build_dual_task_rows()
    single_rows: list[dict] = []
    dual_rows: list[dict] = []
    for task in single_tasks:
        row = dict(task)
        row["spec_time_dry_run"] = fixture_dry_run_result() if use_fixture_only else dry_run_single_task(task)
        single_rows.append(row)
    for task in dual_tasks:
        row = dict(task)
        row["spec_time_dry_run"] = fixture_dry_run_result() if use_fixture_only else dry_run_dual_task(task)
        dual_rows.append(row)
    active_single = [row for row in single_rows if bool((row.get("spec_time_dry_run") or {}).get("target_bucket_hit"))]
    active_dual = [row for row in dual_rows if bool((row.get("spec_time_dry_run") or {}).get("target_bucket_hit"))]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if len(active_single) >= 2 and len({norm(row.get('source_id')) for row in active_single + active_dual}) >= 4 else "FAIL",
        "source_count": len(sources),
        "source_tier_counts": _count_by(sources, "complexity_tier"),
        "single_candidate_task_count": len(single_rows),
        "dual_candidate_task_count": len(dual_rows),
        "single_target_bucket_hit_count": len(active_single),
        "single_target_bucket_hit_rate_pct": round(100.0 * len(active_single) / float(len(single_rows)), 1) if single_rows else 0.0,
        "dual_target_bucket_hit_count": len(active_dual),
        "dual_target_bucket_hit_rate_pct": round(100.0 * len(active_dual) / float(len(dual_rows)), 1) if dual_rows else 0.0,
        "active_single_task_count": len(active_single),
        "active_dual_task_count": len(active_dual),
        "frozen_source_pattern_count": len({norm(row.get("source_id")) for row in active_single + active_dual}),
        "component_family_counts": _count_by(active_single + active_dual, "component_family"),
        "placement_kind_counts": _count_by(active_dual, "placement_kind"),
        "frozen_single_task_ids": [norm(row.get("task_id")) for row in active_single],
        "frozen_dual_task_ids": [norm(row.get("task_id")) for row in active_dual],
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "single_tasks": active_single,
        "dual_tasks": active_dual,
        "single_candidates": single_rows,
        "dual_candidates": dual_rows,
        "pattern_family_counts": {
            "single_component_families": _count_by([dict(row) for row in SINGLE_MISMATCH_SPECS], "component_family"),
            "dual_component_families": _count_by([dict(row) for row in DUAL_RECHECK_SPECS], "component_family"),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "manifest.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.23 Target Manifest",
                "",
                f"- status: `{summary.get('status')}`",
                f"- active_single_task_count: `{summary.get('active_single_task_count')}`",
                f"- active_dual_task_count: `{summary.get('active_dual_task_count')}`",
                f"- frozen_source_pattern_count: `{summary.get('frozen_source_pattern_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.23 local-interface target manifest.")
    parser.add_argument("--out-dir", default=str(DEFAULT_TARGET_MANIFEST_OUT_DIR))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0323_target_manifest(out_dir=str(args.out_dir), use_fixture_only=bool(args.fixture_only))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "active_single_task_count": summary.get("active_single_task_count"), "active_dual_task_count": summary.get("active_dual_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
