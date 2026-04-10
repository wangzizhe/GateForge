from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_3_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V102_CLOSEOUT_PATH,
    READY_MAX_SINGLE_SOURCE_SHARE_PCT,
    READY_MIN_SUBSTRATE_SIZE,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED_VERSION_DECISION = "v0_10_2_real_origin_source_expansion_ready"
EXPECTED_HANDOFF_MODE = "freeze_first_real_origin_workflow_substrate"


def build_v103_handoff_integrity(
    *,
    v102_closeout_path: str = str(DEFAULT_V102_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v102_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}
    source_class_depth = (
        conclusion.get("candidate_depth_by_source_origin_class")
        if isinstance(conclusion.get("candidate_depth_by_source_origin_class"), dict)
        else {}
    )
    upstream_mainline_count = int(conclusion.get("post_expansion_mainline_real_origin_candidate_count") or 0)
    upstream_real_origin_count = int(source_class_depth.get("real_origin") or 0)
    upstream_max_single_source_share_pct = float(conclusion.get("max_single_source_share_pct") or 0.0)

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_VERSION_DECISION,
        "expansion_status_ok": conclusion.get("real_origin_source_expansion_status") == "expansion_ready",
        "mainline_count_ready_ok": upstream_mainline_count >= READY_MIN_SUBSTRATE_SIZE,
        "real_origin_depth_ready_ok": upstream_real_origin_count >= READY_MIN_SUBSTRATE_SIZE,
        "workflow_proxy_zero_ok": int(source_class_depth.get("workflow_proximal_proxy") or 0) == 0,
        "source_concentration_ceiling_ok": upstream_max_single_source_share_pct <= READY_MAX_SINGLE_SOURCE_SHARE_PCT,
        "needs_additional_sources_cleared_ok": not bool(conclusion.get("needs_additional_real_origin_sources")),
        "handoff_mode_ok": conclusion.get("v0_10_3_handoff_mode") == EXPECTED_HANDOFF_MODE,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_real_origin_source_expansion_status": conclusion.get("real_origin_source_expansion_status"),
        "upstream_post_expansion_mainline_real_origin_candidate_count": upstream_mainline_count,
        "upstream_candidate_depth_by_source_origin_class": source_class_depth,
        "upstream_max_single_source_share_pct": upstream_max_single_source_share_pct,
        "upstream_v0_10_3_handoff_mode": conclusion.get("v0_10_3_handoff_mode"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.3 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_post_expansion_mainline_real_origin_candidate_count: `{upstream_mainline_count}`",
                f"- upstream_max_single_source_share_pct: `{upstream_max_single_source_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.3 handoff integrity artifact.")
    parser.add_argument("--v102-closeout", default=str(DEFAULT_V102_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v103_handoff_integrity(v102_closeout_path=str(args.v102_closeout), out_dir=str(args.out_dir))
    print(
        json.dumps(
            {"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
