from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_common import PRIORITY_BARRIERS
from .agent_modelica_v0_9_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V091_CLOSEOUT_PATH,
    READY_BARRIER_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v092_handoff_integrity(
    *,
    v091_closeout_path: str = str(DEFAULT_V091_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v091_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}
    depth = conclusion.get("candidate_depth_by_priority_barrier")
    depth = depth if isinstance(depth, dict) else {}
    checks = {
        "version_decision_ok": conclusion.get("version_decision") == "v0_9_1_real_candidate_source_expansion_ready",
        "source_expansion_status_ok": conclusion.get("candidate_source_expansion_status") == "ready",
        "pool_count_ok": int(conclusion.get("post_expansion_candidate_pool_count") or 0) > 10,
        "priority_barrier_floor_ok": all(int(depth.get(barrier) or 0) >= READY_BARRIER_MIN for barrier in PRIORITY_BARRIERS),
        "handoff_mode_ok": conclusion.get("v0_9_2_handoff_mode") == "freeze_first_expanded_authentic_workflow_substrate",
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_post_expansion_candidate_pool_count": conclusion.get("post_expansion_candidate_pool_count"),
        "upstream_candidate_depth_by_priority_barrier": depth,
        "upstream_v0_9_2_handoff_mode": conclusion.get("v0_9_2_handoff_mode"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.2 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.2 handoff integrity artifact.")
    parser.add_argument("--v091-closeout", default=str(DEFAULT_V091_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v092_handoff_integrity(v091_closeout_path=str(args.v091_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
