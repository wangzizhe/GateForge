from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_7_common import (
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V050_CLOSEOUT_PATH,
    DEFAULT_V051_BOUNDARY_READINESS_PATH,
    DEFAULT_V051_CLOSEOUT_PATH,
    DEFAULT_V056_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_stop_condition_audit"


def build_v057_stop_condition_audit(
    *,
    v050_closeout_path: str = str(DEFAULT_V050_CLOSEOUT_PATH),
    v051_closeout_path: str = str(DEFAULT_V051_CLOSEOUT_PATH),
    v051_boundary_readiness_path: str = str(DEFAULT_V051_BOUNDARY_READINESS_PATH),
    v056_closeout_path: str = str(DEFAULT_V056_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_AUDIT_OUT_DIR),
) -> dict:
    v050 = load_json(v050_closeout_path)
    v051 = load_json(v051_closeout_path)
    readiness = load_json(v051_boundary_readiness_path)
    v056 = load_json(v056_closeout_path)

    wider_real_validation_supported = bool((v050.get("conclusion") or {}).get("dispatch_cleanliness_preserved")) and bool((v050.get("conclusion") or {}).get("qualitative_widening_confirmed"))
    boundary_mapping_supported = bool((v051.get("conclusion") or {}).get("boundary_map_status") == "ready") and bool(readiness.get("boundary_map_ready"))
    bounded_uncovered_handled_to_authority_level = bool((v056.get("conclusion") or {}).get("promotion_supported"))
    phase_not_dependent_on_more_branch_expansion = bool((v056.get("conclusion") or {}).get("recommended_promotion_level") == "family_extension_supported")

    remaining_gap_count = 0
    for flag in [
        wider_real_validation_supported,
        boundary_mapping_supported,
        bounded_uncovered_handled_to_authority_level,
        phase_not_dependent_on_more_branch_expansion,
    ]:
        if not flag:
            remaining_gap_count += 1

    overall_stop_condition_met = remaining_gap_count == 0
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if overall_stop_condition_met else "FAIL",
        "wider_real_validation_supported": wider_real_validation_supported,
        "boundary_mapping_supported": boundary_mapping_supported,
        "bounded_uncovered_handled_to_authority_level": bounded_uncovered_handled_to_authority_level,
        "phase_not_dependent_on_more_branch_expansion": phase_not_dependent_on_more_branch_expansion,
        "remaining_gap_count": remaining_gap_count,
        "overall_stop_condition_met": overall_stop_condition_met,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.7 Stop Condition Audit",
                "",
                f"- overall_stop_condition_met: `{payload.get('overall_stop_condition_met')}`",
                f"- remaining_gap_count: `{payload.get('remaining_gap_count')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.7 stop condition audit.")
    parser.add_argument("--v0-5-0-closeout", default=str(DEFAULT_V050_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-1-closeout", default=str(DEFAULT_V051_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-1-boundary-readiness", default=str(DEFAULT_V051_BOUNDARY_READINESS_PATH))
    parser.add_argument("--v0-5-6-closeout", default=str(DEFAULT_V056_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v057_stop_condition_audit(
        v050_closeout_path=str(args.v0_5_0_closeout),
        v051_closeout_path=str(args.v0_5_1_closeout),
        v051_boundary_readiness_path=str(args.v0_5_1_boundary_readiness),
        v056_closeout_path=str(args.v0_5_6_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "overall_stop_condition_met": payload.get("overall_stop_condition_met")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
