from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_6_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_CLOSEOUT_PATH,
    DEFAULT_V095_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v096_handoff_integrity(
    *,
    v095_closeout_path: str = str(DEFAULT_V095_CLOSEOUT_PATH),
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v095 = load_json(v095_closeout_path)
    v094 = load_json(v094_closeout_path)
    v093 = load_json(v093_closeout_path)
    v092 = load_json(v092_closeout_path)

    c095 = v095.get("conclusion") if isinstance(v095.get("conclusion"), dict) else {}
    c094 = v094.get("conclusion") if isinstance(v094.get("conclusion"), dict) else {}
    c093 = v093.get("conclusion") if isinstance(v093.get("conclusion"), dict) else {}
    c092 = v092.get("conclusion") if isinstance(v092.get("conclusion"), dict) else {}

    checks = {
        "v095_version_decision_ok": c095.get("version_decision")
        == "v0_9_5_expanded_workflow_readiness_partial_but_interpretable",
        "v095_handoff_mode_ok": c095.get("v0_9_6_handoff_mode")
        == "decide_whether_more_authentic_expansion_is_still_worth_it",
        "v095_final_label_ok": c095.get("final_adjudication_label")
        == "expanded_workflow_readiness_partial_but_interpretable",
        "v095_route_count_ok": int(c095.get("adjudication_route_count") or 0) == 1,
        "v095_execution_posture_ok": bool(c095.get("execution_posture_semantics_preserved")),
        "v094_version_decision_ok": c094.get("version_decision")
        == "v0_9_4_expanded_workflow_thresholds_frozen",
        "v093_version_decision_ok": c093.get("version_decision")
        == "v0_9_3_expanded_workflow_profile_characterized",
        "v092_version_decision_ok": c092.get("version_decision")
        == "v0_9_2_first_expanded_authentic_workflow_substrate_ready",
    }
    passed = all(checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": c095.get("version_decision"),
        "upstream_handoff_mode": c095.get("v0_9_6_handoff_mode"),
        "final_adjudication_label": c095.get("final_adjudication_label"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.6 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.6 handoff integrity summary.")
    parser.add_argument("--v095-closeout", default=str(DEFAULT_V095_CLOSEOUT_PATH))
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v096_handoff_integrity(
        v095_closeout_path=str(args.v095_closeout),
        v094_closeout_path=str(args.v094_closeout),
        v093_closeout_path=str(args.v093_closeout),
        v092_closeout_path=str(args.v092_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
