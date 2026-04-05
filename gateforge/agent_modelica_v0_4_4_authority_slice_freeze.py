from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_4_common import (
    DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR,
    DEFAULT_V043_REAL_SLICE_FREEZE_PATH,
    FAMILY_ORDER,
    SCHEMA_PREFIX,
    authority_real_candidates,
    load_json,
    now_utc,
    percent,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_authority_slice_freeze"


def build_v044_authority_slice_freeze(
    *,
    v0_4_3_real_slice_freeze_path: str = str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH),
    out_dir: str = str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR),
) -> dict:
    previous = load_json(v0_4_3_real_slice_freeze_path)
    candidates = authority_real_candidates(previous)

    family_breakdown = {family_id: 0 for family_id in FAMILY_ORDER}
    complexity_breakdown: dict[str, int] = {}
    overlap_case_count = 0
    for row in candidates:
        family_id = str(row.get("family_id") or "")
        family_breakdown[family_id] = int(family_breakdown.get(family_id) or 0) + 1
        complexity = str(row.get("complexity_tier") or "")
        complexity_breakdown[complexity] = int(complexity_breakdown.get(complexity) or 0) + 1
        overlap_case_count += 1 if bool(row.get("authority_overlap_case")) else 0

    previous_task_count = int(previous.get("real_slice_task_count") or 0)
    previous_complex_count = int((previous.get("real_complexity_breakdown") or {}).get("complex") or 0)
    previous_overlap_count = 0
    previous_rows = previous.get("task_rows") if isinstance(previous.get("task_rows"), list) else []
    for row in previous_rows:
        if isinstance(row, dict) and bool(row.get("family_id")):
            from .agent_modelica_v0_4_4_common import authority_overlap_case  # local import to keep file small

            previous_overlap_count += 1 if authority_overlap_case(row) else 0

    complex_density_pct = percent(int(complexity_breakdown.get("complex") or 0), len(candidates))
    previous_complex_density_pct = percent(previous_complex_count, previous_task_count)
    overlap_density_pct = percent(overlap_case_count, len(candidates))
    previous_overlap_density_pct = percent(previous_overlap_count, previous_task_count)

    stronger_dimension_count = sum(
        1
        for condition in (
            complex_density_pct > previous_complex_density_pct,
            overlap_density_pct > previous_overlap_density_pct,
            all(int(family_breakdown.get(family_id) or 0) > 0 for family_id in FAMILY_ORDER),
        )
        if condition
    )

    if len(candidates) >= 15 and all(int(family_breakdown.get(family_id) or 0) > 0 for family_id in FAMILY_ORDER) and stronger_dimension_count >= 1:
        construction_mode = "promoted"
        authority_slice_ready = True
    elif len(candidates) >= 12 and all(int(family_breakdown.get(family_id) or 0) > 0 for family_id in FAMILY_ORDER) and stronger_dimension_count >= 1:
        construction_mode = "degraded_but_executable"
        authority_slice_ready = True
    else:
        construction_mode = "not_ready"
        authority_slice_ready = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if authority_slice_ready else "FAIL",
        "v0_4_3_real_slice_freeze_path": str(Path(v0_4_3_real_slice_freeze_path).resolve()),
        "real_authority_slice_task_count": len(candidates),
        "v0_4_3_real_slice_task_count": previous_task_count,
        "real_authority_family_breakdown": family_breakdown,
        "real_authority_complexity_breakdown": complexity_breakdown,
        "real_authority_overlap_case_count": overlap_case_count,
        "complex_density_pct": complex_density_pct,
        "v0_4_3_complex_density_pct": previous_complex_density_pct,
        "overlap_density_pct": overlap_density_pct,
        "v0_4_3_overlap_density_pct": previous_overlap_density_pct,
        "stronger_dimension_count": stronger_dimension_count,
        "coverage_construction_mode": construction_mode,
        "authority_slice_ready": authority_slice_ready,
        "task_rows": candidates,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_rows.json", {"task_rows": candidates})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.4 Authority Slice Freeze",
                "",
                f"- real_authority_slice_task_count: `{payload.get('real_authority_slice_task_count')}`",
                f"- coverage_construction_mode: `{payload.get('coverage_construction_mode')}`",
                f"- complex_density_pct: `{payload.get('complex_density_pct')}`",
                f"- overlap_density_pct: `{payload.get('overlap_density_pct')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.4 authority slice freeze.")
    parser.add_argument("--v0-4-3-real-slice-freeze", default=str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v044_authority_slice_freeze(
        v0_4_3_real_slice_freeze_path=str(args.v0_4_3_real_slice_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "authority_slice_ready": payload.get("authority_slice_ready"), "real_authority_slice_task_count": payload.get("real_authority_slice_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
