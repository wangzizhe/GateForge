from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_18_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PHASE_CLOSEOUT_OUT_DIR,
    DEFAULT_V180_CLOSEOUT_PATH,
    NEXT_PRIMARY_PHASE_QUESTION,
    REBUILD_PHASE_INPUTS_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_18_1_handoff_integrity import build_v181_handoff_integrity
from .agent_modelica_v0_18_1_phase_closeout import build_v181_phase_closeout


def build_v181_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    phase_closeout_path: str = str(DEFAULT_PHASE_CLOSEOUT_OUT_DIR / "summary.json"),
    v180_closeout_path: str = str(DEFAULT_V180_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    handoff_file = Path(handoff_integrity_path)
    if not handoff_file.exists():
        build_v181_handoff_integrity(v180_closeout_path=v180_closeout_path, out_dir=str(handoff_file.parent))
    handoff = load_json(handoff_integrity_path)

    if str(handoff.get("handoff_integrity_status") or "FAIL") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_18_1_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_18_1_handoff_phase_inputs_invalid",
                "next_primary_phase_question": REBUILD_PHASE_INPUTS_QUESTION,
                "v0_19_primary_phase_question": REBUILD_PHASE_INPUTS_QUESTION,
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.18.1 Closeout\n\n- version_decision: `v0_18_1_handoff_phase_inputs_invalid`\n")
        return payload

    phase_closeout_file = Path(phase_closeout_path)
    if not phase_closeout_file.exists():
        build_v181_phase_closeout(out_dir=str(phase_closeout_file.parent))
    phase_closeout = load_json(phase_closeout_path)

    decision_status = str(phase_closeout.get("phase_closeout_decision_status") or "")
    closeout_needed = bool(phase_closeout.get("closeout_needed"))
    stop_status = str(phase_closeout.get("phase_stop_condition_status") or "")
    explicit_caveat_present = bool(phase_closeout.get("explicit_caveat_present"))
    next_primary_phase_question = str(phase_closeout.get("next_primary_phase_question") or NEXT_PRIMARY_PHASE_QUESTION)
    do_not_continue = bool(phase_closeout.get("do_not_continue_v0_18_same_next_move_loop_by_default"))

    if decision_status == "ready" and not closeout_needed:
        version_decision = "v0_18_phase_closeout_not_needed"
        closeout_status = "V0_18_PHASE_CLOSEOUT_NOT_NEEDED"
        status = "PASS"
        v0_19_primary_phase_question = next_primary_phase_question
    elif decision_status == "ready" and closeout_needed and stop_status == "nearly_complete_with_explicit_caveat" and explicit_caveat_present:
        version_decision = "v0_18_phase_nearly_complete_with_explicit_caveat"
        closeout_status = "V0_18_PHASE_NEARLY_COMPLETE_WITH_EXPLICIT_CAVEAT"
        status = "PASS"
        v0_19_primary_phase_question = next_primary_phase_question
    else:
        version_decision = "v0_18_1_handoff_phase_inputs_invalid"
        closeout_status = "V0_18_1_HANDOFF_PHASE_INPUTS_INVALID"
        status = "FAIL"
        v0_19_primary_phase_question = REBUILD_PHASE_INPUTS_QUESTION

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": version_decision,
            "phase_stop_condition_status": stop_status,
            "explicit_caveat_present": phase_closeout.get("explicit_caveat_present"),
            "explicit_caveat_label": phase_closeout.get("explicit_caveat_label"),
            "next_primary_phase_question": next_primary_phase_question if status == "PASS" else REBUILD_PHASE_INPUTS_QUESTION,
            "do_not_continue_v0_18_same_next_move_loop_by_default": do_not_continue if status == "PASS" else False,
            "why_v0_18_is_or_is_not_phase_complete": phase_closeout.get("why_v0_18_is_or_is_not_phase_complete"),
            "v0_19_primary_phase_question": v0_19_primary_phase_question,
        },
        "handoff_integrity": handoff,
        "phase_closeout": phase_closeout,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.18.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- next_primary_phase_question: `{payload['conclusion']['next_primary_phase_question']}`",
                f"- v0_19_primary_phase_question: `{v0_19_primary_phase_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.18.1 closeout artifact.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--phase-closeout", default=str(DEFAULT_PHASE_CLOSEOUT_OUT_DIR / "summary.json"))
    parser.add_argument("--v180-closeout", default=str(DEFAULT_V180_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v181_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        phase_closeout_path=str(args.phase_closeout),
        v180_closeout_path=str(args.v180_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload["status"], "version_decision": payload["conclusion"]["version_decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
