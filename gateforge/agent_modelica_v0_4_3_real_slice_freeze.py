from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_3_common import (
    DEFAULT_REAL_SLICE_FREEZE_OUT_DIR,
    DEFAULT_V0317_GENERATION_CENSUS_PATH,
    DEFAULT_V042_REAL_BACKCHECK_PATH,
    FAMILY_ORDER,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    widened_real_candidates,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_real_slice_freeze"


def build_v043_real_slice_freeze(
    *,
    generation_census_path: str = str(DEFAULT_V0317_GENERATION_CENSUS_PATH),
    v0_4_2_real_backcheck_path: str = str(DEFAULT_V042_REAL_BACKCHECK_PATH),
    out_dir: str = str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR),
) -> dict:
    generation_census = load_json(generation_census_path)
    previous_backcheck = load_json(v0_4_2_real_backcheck_path)
    candidates = widened_real_candidates(generation_census)

    family_breakdown = {family_id: 0 for family_id in FAMILY_ORDER}
    complexity_breakdown: dict[str, int] = {}
    for row in candidates:
        family_breakdown[str(row.get("family_id") or "")] = int(family_breakdown.get(str(row.get("family_id") or ""), 0)) + 1
        complexity = str(row.get("complexity_tier") or "")
        complexity_breakdown[complexity] = int(complexity_breakdown.get(complexity) or 0) + 1

    previous_count = int(previous_backcheck.get("real_backcheck_task_count") or 0)
    widened_real_slice_ready = len(candidates) > previous_count and all(int(family_breakdown.get(family_id) or 0) > 0 for family_id in FAMILY_ORDER)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if widened_real_slice_ready else "FAIL",
        "generation_census_path": str(Path(generation_census_path).resolve()),
        "v0_4_2_real_backcheck_path": str(Path(v0_4_2_real_backcheck_path).resolve()),
        "real_slice_task_count": len(candidates),
        "v0_4_2_real_slice_task_count": previous_count,
        "real_family_coverage_breakdown": family_breakdown,
        "real_complexity_breakdown": complexity_breakdown,
        "overlap_case_count": len(candidates),
        "widened_real_slice_ready": widened_real_slice_ready,
        "task_rows": candidates,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_rows.json", {"task_rows": candidates})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.3 Real Slice Freeze",
                "",
                f"- real_slice_task_count: `{payload.get('real_slice_task_count')}`",
                f"- v0_4_2_real_slice_task_count: `{payload.get('v0_4_2_real_slice_task_count')}`",
                f"- widened_real_slice_ready: `{payload.get('widened_real_slice_ready')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.3 widened real slice freeze.")
    parser.add_argument("--generation-census", default=str(DEFAULT_V0317_GENERATION_CENSUS_PATH))
    parser.add_argument("--v0-4-2-real-backcheck", default=str(DEFAULT_V042_REAL_BACKCHECK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v043_real_slice_freeze(
        generation_census_path=str(args.generation_census),
        v0_4_2_real_backcheck_path=str(args.v0_4_2_real_backcheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "real_slice_task_count": payload.get("real_slice_task_count"), "widened_real_slice_ready": payload.get("widened_real_slice_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
