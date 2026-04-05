from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_0_common import (
    DEFAULT_V043_REAL_SLICE_FREEZE_PATH,
    DEFAULT_V046_CLOSEOUT_PATH,
    DEFAULT_WIDENED_SPEC_OUT_DIR,
    MINIMUM_CASE_DELTA_VS_V04_TARGETED,
    MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT,
    MINIMUM_OVERLAP_CASE_REQUIREMENT,
    MINIMUM_QUALITATIVE_CASE_COUNT,
    MINIMUM_QUALITATIVE_CASE_SHARE_PCT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_widened_spec"


def build_v050_widened_spec(
    *,
    v0_4_3_real_slice_freeze_path: str = str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH),
    v0_4_6_closeout_path: str = str(DEFAULT_V046_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_WIDENED_SPEC_OUT_DIR),
) -> dict:
    real_slice = load_json(v0_4_3_real_slice_freeze_path)
    closeout = load_json(v0_4_6_closeout_path)

    prior_targeted_count = int(real_slice.get("v0_4_2_real_slice_task_count") or 0)
    widened_count = int(real_slice.get("real_slice_task_count") or 0)
    minimum_case_delta = MINIMUM_CASE_DELTA_VS_V04_TARGETED

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "source_real_slice_freeze_path": str(Path(v0_4_3_real_slice_freeze_path).resolve()),
        "source_phase_closeout_path": str(Path(v0_4_6_closeout_path).resolve()),
        "widened_slice_spec_ready": True,
        "v0_4_phase_status": ((closeout.get("conclusion") or {}).get("phase_status")),
        "v0_4_targeted_real_slice_task_count": prior_targeted_count,
        "reference_widened_candidate_count": widened_count,
        "quantitative_widening_required": True,
        "qualitative_widening_required": True,
        "minimum_case_delta_vs_v0_4_targeted": minimum_case_delta,
        "minimum_qualitative_case_count": MINIMUM_QUALITATIVE_CASE_COUNT,
        "minimum_qualitative_case_share_pct": MINIMUM_QUALITATIVE_CASE_SHARE_PCT,
        "minimum_distinct_qualitative_bucket_count": MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT,
        "minimum_overlap_case_requirement": MINIMUM_OVERLAP_CASE_REQUIREMENT,
        "floor_interpretation": "minimum_acceptable_floor",
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.0 Widened Spec",
                "",
                f"- v0_4_targeted_real_slice_task_count: `{prior_targeted_count}`",
                f"- minimum_case_delta_vs_v0_4_targeted: `{minimum_case_delta}`",
                f"- minimum_qualitative_case_count: `{MINIMUM_QUALITATIVE_CASE_COUNT}`",
                f"- minimum_qualitative_case_share_pct: `{MINIMUM_QUALITATIVE_CASE_SHARE_PCT}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.0 widened real-distribution spec.")
    parser.add_argument("--v0-4-3-real-slice-freeze", default=str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH))
    parser.add_argument("--v0-4-6-closeout", default=str(DEFAULT_V046_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_WIDENED_SPEC_OUT_DIR))
    args = parser.parse_args()
    payload = build_v050_widened_spec(
        v0_4_3_real_slice_freeze_path=str(args.v0_4_3_real_slice_freeze),
        v0_4_6_closeout_path=str(args.v0_4_6_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "widened_slice_spec_ready": payload.get("widened_slice_spec_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
