from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_6_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V105_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v106_handoff_integrity(
    *,
    v105_closeout_path: str = str(DEFAULT_V105_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v105_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    threshold_pack = (
        closeout.get("first_real_origin_threshold_pack")
        if isinstance(closeout.get("first_real_origin_threshold_pack"), dict)
        else {}
    )

    checks = {
        "version_decision_matches": conclusion.get("version_decision")
        == "v0_10_5_first_real_origin_workflow_thresholds_frozen",
        "handoff_mode_expected": conclusion.get("v0_10_6_handoff_mode")
        == "adjudicate_first_real_origin_workflow_readiness_against_frozen_thresholds",
        "baseline_classification_ok": conclusion.get("baseline_classification_under_frozen_pack")
        == "real_origin_workflow_readiness_partial_but_interpretable",
        "anti_tautology_ok": bool(conclusion.get("anti_tautology_pass")),
        "integer_safe_ok": bool(conclusion.get("integer_safe_pass")),
        "execution_posture_ok": bool(threshold_pack.get("execution_posture_semantics_preserved")),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "v105_closeout_summary": {
            "version_decision": conclusion.get("version_decision"),
            "baseline_classification_under_frozen_pack": conclusion.get("baseline_classification_under_frozen_pack"),
            "anti_tautology_pass": conclusion.get("anti_tautology_pass"),
            "integer_safe_pass": conclusion.get("integer_safe_pass"),
            "v0_10_6_handoff_mode": conclusion.get("v0_10_6_handoff_mode"),
        },
        "v105_threshold_pack_summary": {
            "execution_posture_semantics_preserved": threshold_pack.get("execution_posture_semantics_preserved"),
            "supported_thresholds": threshold_pack.get("supported_thresholds"),
            "partial_thresholds": threshold_pack.get("partial_thresholds"),
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.6 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- version_decision: `{conclusion.get('version_decision')}`",
                f"- v0_10_6_handoff_mode: `{conclusion.get('v0_10_6_handoff_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.6 handoff integrity artifact.")
    parser.add_argument("--v105-closeout", default=str(DEFAULT_V105_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v106_handoff_integrity(
        v105_closeout_path=str(args.v105_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
