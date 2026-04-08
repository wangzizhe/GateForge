from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_2_common import evaluate_rule_pack
from .agent_modelica_v0_8_4_common import (
    DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR,
    DEFAULT_V082_THRESHOLD_FREEZE_PATH,
    DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v084_frozen_baseline_adjudication(
    *,
    v082_threshold_input_table_path: str = str(DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH),
    v082_threshold_freeze_path: str = str(DEFAULT_V082_THRESHOLD_FREEZE_PATH),
    out_dir: str = str(DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR),
) -> dict:
    threshold_input = load_json(v082_threshold_input_table_path)
    threshold_freeze = load_json(v082_threshold_freeze_path)

    metrics = dict(threshold_input.get("frozen_baseline_metrics") or {})
    supported_pack = threshold_freeze.get("supported_threshold_pack") or {}
    partial_pack = threshold_freeze.get("partial_threshold_pack") or {}

    supported = evaluate_rule_pack(metrics, supported_pack)
    partial = evaluate_rule_pack(metrics, partial_pack)
    fallback = not supported and not partial
    route_count = int(sum([bool(supported), bool(partial), bool(fallback)]))

    if route_count == 1:
        if supported:
            route = "workflow_readiness_supported"
        elif partial:
            route = "workflow_readiness_partial_but_interpretable"
        else:
            route = "fallback_to_error_distribution_hardening_needed"
    else:
        route = "invalid_non_unique_route"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_frozen_baseline_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if route_count == 1 else "FAIL",
        "threshold_pack_status_reconfirmed": threshold_freeze.get("threshold_pack_status"),
        "execution_source": "gateforge_run_contract_live_path",
        "workflow_resolution_rate_pct": metrics.get("workflow_resolution_rate_pct"),
        "goal_alignment_rate_pct": metrics.get("goal_alignment_rate_pct"),
        "surface_fix_only_rate_pct": metrics.get("surface_fix_only_rate_pct"),
        "unresolved_rate_pct": metrics.get("unresolved_rate_pct"),
        "workflow_spillover_share_pct": metrics.get("workflow_spillover_share_pct"),
        "dispatch_or_policy_limited_share_pct": metrics.get("dispatch_or_policy_limited_share_pct"),
        "goal_artifact_missing_after_surface_fix_share_pct": metrics.get(
            "goal_artifact_missing_after_surface_fix_share_pct"
        ),
        "supported_rule_passed": supported,
        "partial_rule_passed": partial,
        "fallback_rule_passed": fallback,
        "adjudication_route_count": route_count,
        "adjudication_route": route,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.4 Frozen Baseline Adjudication",
                "",
                f"- adjudication_route: `{payload['adjudication_route']}`",
                f"- adjudication_route_count: `{payload['adjudication_route_count']}`",
                f"- workflow_resolution_rate_pct: `{payload['workflow_resolution_rate_pct']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.4 frozen baseline adjudication artifact.")
    parser.add_argument("--v082-threshold-input-table", default=str(DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH))
    parser.add_argument("--v082-threshold-freeze", default=str(DEFAULT_V082_THRESHOLD_FREEZE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v084_frozen_baseline_adjudication(
        v082_threshold_input_table_path=str(args.v082_threshold_input_table),
        v082_threshold_freeze_path=str(args.v082_threshold_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "adjudication_route": payload.get("adjudication_route")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
