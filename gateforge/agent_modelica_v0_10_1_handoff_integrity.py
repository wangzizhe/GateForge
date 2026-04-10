from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V1000_CLOSEOUT_PATH,
    PROMOTED_MAINLINE_MIN_COUNT,
    PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED_VERSION_DECISION = "v0_10_0_real_origin_candidate_governance_partial"
EXPECTED_HANDOFF_MODE = "expand_real_origin_candidate_pool_before_substrate_freeze"


def build_v101_handoff_integrity(
    *,
    v1000_closeout_path: str = str(DEFAULT_V1000_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v1000_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}
    depth_probe = upstream.get("depth_probe") if isinstance(upstream.get("depth_probe"), dict) else {}

    source_class_depth = (
        conclusion.get("candidate_depth_by_source_origin_class")
        if isinstance(conclusion.get("candidate_depth_by_source_origin_class"), dict)
        else {}
    )
    upstream_mainline_count = int(conclusion.get("mainline_real_origin_candidate_count") or 0)
    upstream_max_single_source_share_pct = float(
        conclusion.get("max_single_source_share_pct")
        or depth_probe.get("max_single_source_share_pct")
        or 0.0
    )

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_VERSION_DECISION,
        "governance_status_ok": conclusion.get("real_origin_candidate_governance_status") == "governance_partial",
        "mainline_count_below_promoted_floor_ok": upstream_mainline_count < PROMOTED_MAINLINE_MIN_COUNT,
        "workflow_proxy_zero_ok": int(source_class_depth.get("workflow_proximal_proxy") or 0) == 0,
        "source_concentration_above_promoted_floor_ok": upstream_max_single_source_share_pct
        > PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT,
        "needs_additional_sources_ok": bool(conclusion.get("needs_additional_real_origin_sources")),
        "handoff_mode_ok": conclusion.get("v0_10_1_handoff_mode") == EXPECTED_HANDOFF_MODE,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_real_origin_candidate_governance_status": conclusion.get("real_origin_candidate_governance_status"),
        "upstream_mainline_real_origin_candidate_count": upstream_mainline_count,
        "upstream_candidate_depth_by_source_origin_class": source_class_depth,
        "upstream_max_single_source_share_pct": upstream_max_single_source_share_pct,
        "upstream_v0_10_1_handoff_mode": conclusion.get("v0_10_1_handoff_mode"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_mainline_real_origin_candidate_count: `{upstream_mainline_count}`",
                f"- upstream_max_single_source_share_pct: `{upstream_max_single_source_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.1 handoff integrity artifact.")
    parser.add_argument("--v1000-closeout", default=str(DEFAULT_V1000_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v101_handoff_integrity(v1000_closeout_path=str(args.v1000_closeout), out_dir=str(args.out_dir))
    print(
        json.dumps(
            {"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
