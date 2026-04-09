from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V090_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED_VERSION_DECISION = "v0_9_0_candidate_pool_governance_partial"
EXPECTED_HANDOFF_MODE = "expand_real_candidate_pool_before_substrate_freeze"
EXPECTED_BASELINE_DEPTH = {
    "goal_artifact_missing_after_surface_fix": 2,
    "dispatch_or_policy_limited_unresolved": 2,
    "workflow_spillover_unresolved": 2,
}


def build_v091_handoff_integrity(
    *,
    v090_closeout_path: str = str(DEFAULT_V090_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v090_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}
    depth = conclusion.get("candidate_depth_by_priority_barrier")
    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_VERSION_DECISION,
        "governance_status_ok": conclusion.get("candidate_pool_governance_status") == "partial",
        "needs_additional_sources_ok": bool(conclusion.get("needs_additional_real_sources")),
        "handoff_mode_ok": conclusion.get("v0_9_1_handoff_mode") == EXPECTED_HANDOFF_MODE,
        "baseline_depth_ok": depth == EXPECTED_BASELINE_DEPTH,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_candidate_pool_governance_status": conclusion.get("candidate_pool_governance_status"),
        "upstream_candidate_depth_by_priority_barrier": depth,
        "upstream_v0_9_1_handoff_mode": conclusion.get("v0_9_1_handoff_mode"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.1 handoff integrity artifact.")
    parser.add_argument("--v090-closeout", default=str(DEFAULT_V090_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v091_handoff_integrity(v090_closeout_path=str(args.v090_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
