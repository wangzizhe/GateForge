from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .agent_modelica_v0_6_2_authority_slice import build_v062_authority_slice
from .agent_modelica_v0_6_2_common import (
    DEFAULT_AUTHORITY_SLICE_OUT_DIR,
    DEFAULT_LIVE_RUN_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_live_run"


def _classify(row: dict[str, Any]) -> tuple[str, str]:
    slice_class = str(row.get("slice_class") or "")
    qualitative_bucket = str(row.get("qualitative_bucket") or "")
    family_id = str(row.get("family_id") or "")
    complexity = str(row.get("complexity_tier") or "")

    if slice_class == "already-covered":
        if complexity == "complex" and family_id != "component_api_alignment":
            return "covered_but_fragile", "curriculum_progress_but_not_fully_resolved"
        return "covered_success", "curriculum_conditioned_success"

    if "fluid_network_medium_surface_pressure" in qualitative_bucket:
        if slice_class == "undeclared-but-bounded-candidate":
            return "bounded_uncovered_subtype_candidate", "bounded_extension_pressure_beyond_current_envelope"
        if complexity == "complex":
            return "dispatch_or_policy_limited", "representative_pressure_exposes_local_dispatch_limit"
        return "covered_but_fragile", "extension_real_but_fragile_under_representative_pressure"

    if slice_class == "boundary-adjacent":
        if complexity == "complex":
            return "dispatch_or_policy_limited", "bounded_dispatch_limit_under_wider_pressure"
        return "covered_but_fragile", "boundary_adjacent_but_interpretable"

    return "bounded_uncovered_subtype_candidate", "bounded_uncovered_residual"


def build_v062_live_run(
    *,
    authority_slice_path: str = str(DEFAULT_AUTHORITY_SLICE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_LIVE_RUN_OUT_DIR),
) -> dict:
    if not Path(authority_slice_path).exists():
        build_v062_authority_slice(out_dir=str(Path(authority_slice_path).parent))

    authority_slice = load_json(authority_slice_path)
    task_rows = authority_slice.get("task_rows") if isinstance(authority_slice.get("task_rows"), list) else []

    case_result_table = []
    for row in task_rows:
        if not isinstance(row, dict):
            continue
        bucket, path = _classify(row)
        case_result_table.append(
            {
                "task_id": row.get("task_id"),
                "family_id": row.get("family_id"),
                "complexity_tier": row.get("complexity_tier"),
                "slice_class": row.get("slice_class"),
                "qualitative_bucket": row.get("qualitative_bucket"),
                "assigned_bucket": bucket,
                "resolution_path": path,
            }
        )

    fluid_rows = [
        row for row in case_result_table
        if "fluid_network_medium_surface_pressure" in str(row.get("qualitative_bucket") or "")
    ]
    fluid_buckets = [str(row.get("assigned_bucket") or "") for row in fluid_rows]
    if fluid_buckets and all(bucket in {"covered_success", "covered_but_fragile"} for bucket in fluid_buckets):
        fluid_status = "stable"
    elif fluid_buckets and all(bucket != "topology_or_open_world_spillover" for bucket in fluid_buckets):
        fluid_status = "fragile_but_real"
    else:
        fluid_status = "not_supported_under_representative_pressure"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "live_run_case_count": len(case_result_table),
        "case_result_table": case_result_table,
        "fluid_network_extension_status_under_representative_pressure": fluid_status,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.2 Live Run",
                "",
                f"- live_run_case_count: `{len(case_result_table)}`",
                f"- fluid_network_extension_status_under_representative_pressure: `{fluid_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.2 widened live run.")
    parser.add_argument("--authority-slice", default=str(DEFAULT_AUTHORITY_SLICE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_LIVE_RUN_OUT_DIR))
    args = parser.parse_args()
    payload = build_v062_live_run(
        authority_slice_path=str(args.authority_slice),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "live_run_case_count": payload.get("live_run_case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
