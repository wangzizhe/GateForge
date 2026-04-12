from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_2_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR,
    DEFAULT_STRONGER_REMEDY_SCOPE_SUMMARY_OUT_DIR,
    DEFAULT_V121_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    STRONGER_REMEDY_STATUS_JUSTIFIED,
    STRONGER_REMEDY_STATUS_NOT_IN_SCOPE,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_12_2_handoff_integrity import build_v122_handoff_integrity
from .agent_modelica_v0_12_2_remaining_remedy_scope_assessment import build_v122_remaining_remedy_scope_assessment
from .agent_modelica_v0_12_2_stronger_remedy_scope_summary import build_v122_stronger_remedy_scope_summary


def build_v122_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    remaining_remedy_scope_assessment_path: str = str(
        DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR / "summary.json"
    ),
    stronger_remedy_scope_summary_path: str = str(
        DEFAULT_STRONGER_REMEDY_SCOPE_SUMMARY_OUT_DIR / "summary.json"
    ),
    v121_closeout_path: str = str(DEFAULT_V121_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    # Build handoff integrity if not present
    handoff_path_obj = Path(handoff_integrity_path)
    if not handoff_path_obj.exists():
        build_v122_handoff_integrity(
            v121_closeout_path=v121_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)

    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_12_2_OPERATIONAL_REMEDY_SCOPE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_12_2_operational_remedy_scope_inputs_invalid",
                "stronger_remedy_scope_status": "invalid",
                "v0_12_3_handoff_mode": "rebuild_v0_12_2_scope_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.12.2 Closeout\n\n- version_decision: `v0_12_2_operational_remedy_scope_inputs_invalid`\n")
        return payload

    # Build scope assessment if not present
    scope_assessment_path_obj = Path(remaining_remedy_scope_assessment_path)
    if not scope_assessment_path_obj.exists():
        build_v122_remaining_remedy_scope_assessment(
            v121_closeout_path=v121_closeout_path,
            out_dir=str(scope_assessment_path_obj.parent),
        )

    # Build scope summary if not present
    scope_summary_path_obj = Path(stronger_remedy_scope_summary_path)
    if not scope_summary_path_obj.exists():
        build_v122_stronger_remedy_scope_summary(
            remaining_remedy_scope_assessment_path=remaining_remedy_scope_assessment_path,
            out_dir=str(scope_summary_path_obj.parent),
        )

    scope_summary = load_json(stronger_remedy_scope_summary_path)
    stronger_remedy_scope_status = str(scope_summary.get("stronger_remedy_scope_status") or "")
    candidate_obj = (
        scope_summary.get("stronger_remedy_candidate_object")
        if isinstance(scope_summary.get("stronger_remedy_candidate_object"), dict)
        else {}
    )
    scope_obj = (
        scope_summary.get("remaining_remedy_scope_object")
        if isinstance(scope_summary.get("remaining_remedy_scope_object"), dict)
        else {}
    )

    # Route table (plan § Step 4)
    if stronger_remedy_scope_status == STRONGER_REMEDY_STATUS_JUSTIFIED:
        version_decision = "v0_12_2_stronger_bounded_remedy_justified"
        handoff_mode = "execute_stronger_bounded_operational_remedy"
        status = "PASS"
    elif stronger_remedy_scope_status == STRONGER_REMEDY_STATUS_NOT_IN_SCOPE:
        version_decision = "v0_12_2_stronger_bounded_remedy_not_in_scope"
        handoff_mode = "prepare_v0_12_phase_synthesis"
        status = "PASS"
    else:
        version_decision = "v0_12_2_operational_remedy_scope_inputs_invalid"
        handoff_mode = "rebuild_v0_12_2_scope_inputs_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "stronger_remedy_scope_status": stronger_remedy_scope_status,
            "expected_information_gain": scope_obj.get("expected_information_gain"),
            "candidate_remedy_id": candidate_obj.get("candidate_remedy_id"),
            "candidate_remedy_shape": candidate_obj.get("candidate_remedy_shape"),
            "named_blocker_if_not_in_scope": scope_summary.get("named_blocker_if_not_in_scope"),
            "v0_12_3_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "stronger_remedy_scope_summary": scope_summary,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- stronger_remedy_scope_status: `{stronger_remedy_scope_status}`",
                f"- v0_12_3_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.2 scope adjudication closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--remaining-remedy-scope-assessment",
        default=str(DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--stronger-remedy-scope-summary",
        default=str(DEFAULT_STRONGER_REMEDY_SCOPE_SUMMARY_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v121-closeout", default=str(DEFAULT_V121_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v122_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        remaining_remedy_scope_assessment_path=str(args.remaining_remedy_scope_assessment),
        stronger_remedy_scope_summary_path=str(args.stronger_remedy_scope_summary),
        v121_closeout_path=str(args.v121_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "version_decision": (payload.get("conclusion") or {}).get("version_decision"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
