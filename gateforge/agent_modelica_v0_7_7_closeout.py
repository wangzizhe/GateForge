"""Block E: Phase Closeout.

Orchestrates Blocks A–D and applies the routing hard-rules from PLAN_V0_7_7
to produce the v0.7.7 version_decision and v0.8.x handoff spec.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_7_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V070_CLOSEOUT_PATH,
    DEFAULT_V071_CLOSEOUT_PATH,
    DEFAULT_V072_CLOSEOUT_PATH,
    DEFAULT_V073_CLOSEOUT_PATH,
    DEFAULT_V074_CLOSEOUT_PATH,
    DEFAULT_V075_CLOSEOUT_PATH,
    DEFAULT_V076_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_7_7_meaning_synthesis import build_v077_meaning_synthesis
from .agent_modelica_v0_7_7_phase_ledger import build_v077_phase_ledger
from .agent_modelica_v0_7_7_stop_condition import build_v077_stop_condition

_STOP_STATUS_TO_VERSION_DECISION = {
    "phase_stop_condition_met": "v0_7_phase_complete_prepare_v0_8",
    "nearly_complete_with_caveat": "v0_7_phase_nearly_complete_with_explicit_caveat",
    "not_ready_for_closeout": "v0_7_phase_not_ready_for_closeout",
}

_STOP_STATUS_TO_PHASE_STATUS = {
    "phase_stop_condition_met": "complete",
    "nearly_complete_with_caveat": "nearly_complete",
    "not_ready_for_closeout": "not_ready",
}

_STOP_STATUS_TO_HANDOFF_MODE = {
    "phase_stop_condition_met": "run_v0_8_phase_synthesis",
    "nearly_complete_with_caveat": "run_v0_8_with_explicit_caveat_carried_forward",
    "not_ready_for_closeout": "continue_v0_7_x",
}


def build_v077_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_condition_path: str = str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"),
    meaning_synthesis_path: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"),
    v070_closeout_path: str = str(DEFAULT_V070_CLOSEOUT_PATH),
    v071_closeout_path: str = str(DEFAULT_V071_CLOSEOUT_PATH),
    v072_closeout_path: str = str(DEFAULT_V072_CLOSEOUT_PATH),
    v073_closeout_path: str = str(DEFAULT_V073_CLOSEOUT_PATH),
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    v075_closeout_path: str = str(DEFAULT_V075_CLOSEOUT_PATH),
    v076_closeout_path: str = str(DEFAULT_V076_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    # Always rebuild A-D during closeout so stale intermediate artifacts cannot
    # lag behind updated upstream closeouts.
    build_v077_phase_ledger(
        v070_closeout_path=v070_closeout_path,
        v071_closeout_path=v071_closeout_path,
        v072_closeout_path=v072_closeout_path,
        v073_closeout_path=v073_closeout_path,
        v074_closeout_path=v074_closeout_path,
        v075_closeout_path=v075_closeout_path,
        v076_closeout_path=v076_closeout_path,
        out_dir=str(Path(phase_ledger_path).parent),
    )
    ledger = load_json(phase_ledger_path)

    if ledger.get("phase_ledger_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_7_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_7_handoff_substrate_invalid",
                "phase_status": "invalid",
                "phase_primary_question_answered": False,
                "deferred_questions_non_blocking": False,
                "v0_8_handoff_mode": "repair_v0_7_x_phase_ledger_first",
                "v0_8_handoff_spec": None,
                "do_not_continue_v0_7_same_logic_refinement_by_default": True,
            },
            "phase_ledger": ledger,
        }
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "\n".join(
                [
                    "# v0.7.7 Closeout",
                    "",
                    "- version_decision: `v0_7_7_handoff_substrate_invalid`",
                    "- phase_status: `invalid`",
                    "- v0_8_handoff_mode: `repair_v0_7_x_phase_ledger_first`",
                ]
            ),
        )
        return payload

    # Block B: Stop-Condition Audit.
    build_v077_stop_condition(
        v070_closeout_path=v070_closeout_path,
        v071_closeout_path=v071_closeout_path,
        v072_closeout_path=v072_closeout_path,
        v074_closeout_path=v074_closeout_path,
        v076_closeout_path=v076_closeout_path,
        out_dir=str(Path(stop_condition_path).parent),
    )
    stop = load_json(stop_condition_path)

    # Block C + D: Meaning Synthesis.
    build_v077_meaning_synthesis(
        v075_closeout_path=v075_closeout_path,
        v076_closeout_path=v076_closeout_path,
        out_dir=str(Path(meaning_synthesis_path).parent),
    )
    synthesis = load_json(meaning_synthesis_path)

    stop_status = str(stop.get("phase_stop_condition_status") or "not_ready_for_closeout")
    version_decision = _STOP_STATUS_TO_VERSION_DECISION.get(
        stop_status, "v0_7_phase_not_ready_for_closeout"
    )
    phase_status = _STOP_STATUS_TO_PHASE_STATUS.get(stop_status, "not_ready")
    handoff_mode = _STOP_STATUS_TO_HANDOFF_MODE.get(stop_status, "continue_v0_7_x")

    phase_primary_question_answered = stop_status in (
        "phase_stop_condition_met",
        "nearly_complete_with_caveat",
    )
    deferred_questions_non_blocking = stop_status in (
        "phase_stop_condition_met",
        "nearly_complete_with_caveat",
    )

    v0_8_primary_question = synthesis.get("v0_8_primary_phase_question")
    v0_8_handoff_spec = {
        "v0_8_primary_phase_question": v0_8_primary_question,
        "why_not_the_other_candidates": synthesis.get("why_not_the_other_candidates"),
        "carries_caveat": stop_status == "nearly_complete_with_caveat",
    } if phase_primary_question_answered else None

    is_pass = stop_status in ("phase_stop_condition_met", "nearly_complete_with_caveat")

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if is_pass else "FAIL",
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "phase_status": phase_status,
            "phase_primary_question_answered": phase_primary_question_answered,
            "deferred_questions_non_blocking": deferred_questions_non_blocking,
            "v0_8_handoff_mode": handoff_mode,
            "v0_8_handoff_spec": v0_8_handoff_spec,
            "do_not_continue_v0_7_same_logic_refinement_by_default": True,
        },
        "phase_ledger": ledger,
        "stop_condition": stop,
        "meaning_synthesis": synthesis,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.7 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- phase_status: `{phase_status}`",
                f"- phase_primary_question_answered: `{phase_primary_question_answered}`",
                f"- deferred_questions_non_blocking: `{deferred_questions_non_blocking}`",
                f"- v0_8_handoff_mode: `{handoff_mode}`",
                f"- v0_8_primary_phase_question: `{v0_8_primary_question}`",
                f"- do_not_continue_v0_7_same_logic_refinement_by_default: `True`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.7 phase synthesis closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-condition", default=str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"))
    parser.add_argument("--meaning-synthesis", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--v070-closeout", default=str(DEFAULT_V070_CLOSEOUT_PATH))
    parser.add_argument("--v071-closeout", default=str(DEFAULT_V071_CLOSEOUT_PATH))
    parser.add_argument("--v072-closeout", default=str(DEFAULT_V072_CLOSEOUT_PATH))
    parser.add_argument("--v073-closeout", default=str(DEFAULT_V073_CLOSEOUT_PATH))
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--v075-closeout", default=str(DEFAULT_V075_CLOSEOUT_PATH))
    parser.add_argument("--v076-closeout", default=str(DEFAULT_V076_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v077_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_condition_path=str(args.stop_condition),
        meaning_synthesis_path=str(args.meaning_synthesis),
        v070_closeout_path=str(args.v070_closeout),
        v071_closeout_path=str(args.v071_closeout),
        v072_closeout_path=str(args.v072_closeout),
        v073_closeout_path=str(args.v073_closeout),
        v074_closeout_path=str(args.v074_closeout),
        v075_closeout_path=str(args.v075_closeout),
        v076_closeout_path=str(args.v076_closeout),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "version_decision": (payload.get("conclusion") or {}).get("version_decision"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
