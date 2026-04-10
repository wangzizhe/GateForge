from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_7_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V106_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v107_handoff_integrity(
    *,
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v106_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}

    checks = {
        "version_decision_matches": conclusion.get("version_decision")
        == "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable",
        "final_adjudication_label_ok": conclusion.get("final_adjudication_label")
        == "real_origin_workflow_readiness_partial_but_interpretable",
        "supported_check_false": bool(conclusion.get("supported_check_pass")) is False,
        "partial_check_true": bool(conclusion.get("partial_check_pass")) is True,
        "fallback_trigger_false": bool(conclusion.get("fallback_triggered")) is False,
        "execution_posture_ok": bool(conclusion.get("execution_posture_semantics_preserved")),
        "handoff_mode_expected": conclusion.get("v0_10_7_handoff_mode")
        == "decide_whether_one_more_bounded_real_origin_step_is_still_worth_it",
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "v106_closeout_summary": {
            "version_decision": conclusion.get("version_decision"),
            "final_adjudication_label": conclusion.get("final_adjudication_label"),
            "supported_check_pass": conclusion.get("supported_check_pass"),
            "partial_check_pass": conclusion.get("partial_check_pass"),
            "fallback_triggered": conclusion.get("fallback_triggered"),
            "execution_posture_semantics_preserved": conclusion.get("execution_posture_semantics_preserved"),
            "v0_10_7_handoff_mode": conclusion.get("v0_10_7_handoff_mode"),
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.7 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- version_decision: `{conclusion.get('version_decision')}`",
                f"- v0_10_7_handoff_mode: `{conclusion.get('v0_10_7_handoff_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.7 handoff integrity artifact.")
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v107_handoff_integrity(
        v106_closeout_path=str(args.v106_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
