from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH,
    MIN_REAL_ORIGIN_SOURCE_COUNT,
    MIN_REAL_ORIGIN_SUBSTRATE_SIZE,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v104_handoff_integrity(
    *,
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v103_real_origin_substrate_builder_path: str = str(DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v103_closeout_path)
    builder = load_json(v103_real_origin_substrate_builder_path)

    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    source_coverage_table = (
        conclusion.get("source_coverage_table") if isinstance(conclusion.get("source_coverage_table"), dict) else {}
    )
    builder_rows = (
        builder.get("real_origin_substrate_candidate_table")
        if isinstance(builder.get("real_origin_substrate_candidate_table"), list)
        else []
    )
    builder_source_mix = builder.get("source_mix") if isinstance(builder.get("source_mix"), dict) else {}

    checks = {
        "closeout_version_ready": conclusion.get("version_decision")
        == "v0_10_3_first_real_origin_workflow_substrate_ready",
        "closeout_substrate_ready": conclusion.get("real_origin_substrate_admission_status") == "ready",
        "closeout_size_floor_met": int(conclusion.get("real_origin_substrate_size") or 0) >= MIN_REAL_ORIGIN_SUBSTRATE_SIZE,
        "closeout_source_floor_met": len([k for k, v in source_coverage_table.items() if int(v) > 0]) >= MIN_REAL_ORIGIN_SOURCE_COUNT,
        "closeout_source_diversity_ok": float(conclusion.get("max_single_source_share_pct") or 0.0) <= 50.0,
        "closeout_handoff_mode_expected": conclusion.get("v0_10_4_handoff_mode")
        == "characterize_first_real_origin_workflow_profile",
        "builder_exists_and_size_floor_met": len(builder_rows) >= MIN_REAL_ORIGIN_SUBSTRATE_SIZE,
        "builder_source_floor_met": len([k for k, v in builder_source_mix.items() if int(v) > 0]) >= MIN_REAL_ORIGIN_SOURCE_COUNT,
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "v103_closeout_summary": {
            "version_decision": conclusion.get("version_decision"),
            "real_origin_substrate_size": conclusion.get("real_origin_substrate_size"),
            "source_coverage_table": source_coverage_table,
            "max_single_source_share_pct": conclusion.get("max_single_source_share_pct"),
            "real_origin_substrate_admission_status": conclusion.get("real_origin_substrate_admission_status"),
            "v0_10_4_handoff_mode": conclusion.get("v0_10_4_handoff_mode"),
        },
        "v103_real_origin_substrate_builder_summary": {
            "real_origin_substrate_candidate_count": len(builder_rows),
            "source_mix": builder_source_mix,
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.4 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- real_origin_substrate_candidate_count: `{len(builder_rows)}`",
                f"- source_mix: `{builder_source_mix}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.4 handoff integrity artifact.")
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v103-real-origin-substrate-builder", default=str(DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v104_handoff_integrity(
        v103_closeout_path=str(args.v103_closeout),
        v103_real_origin_substrate_builder_path=str(args.v103_real_origin_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
