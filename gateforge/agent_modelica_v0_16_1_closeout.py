from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_16_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V160_CLOSEOUT_PATH,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_16_1_meaning_synthesis import build_v161_meaning_synthesis
from .agent_modelica_v0_16_1_phase_ledger import build_v161_phase_ledger
from .agent_modelica_v0_16_1_stop_condition import build_v161_stop_condition


def build_v161_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_condition_path: str = str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"),
    meaning_synthesis_path: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"),
    v160_closeout_path: str = str(DEFAULT_V160_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    phase_ledger_file = Path(phase_ledger_path)
    if not phase_ledger_file.exists():
        build_v161_phase_ledger(
            v160_closeout_path=v160_closeout_path,
            out_dir=str(phase_ledger_file.parent),
        )
    ledger = load_json(phase_ledger_path)

    if ledger.get("phase_ledger_status") == "invalid":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_16_1_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_16_1_handoff_phase_inputs_invalid",
                "v0_17_primary_phase_question": "rebuild_v0_16_phase_inputs_first",
            },
            "phase_ledger": ledger,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.16.1 Closeout\n\n- version_decision: `v0_16_1_handoff_phase_inputs_invalid`\n")
        return payload

    stop_condition_file = Path(stop_condition_path)
    if not stop_condition_file.exists():
        build_v161_stop_condition(
            v160_closeout_path=v160_closeout_path,
            out_dir=str(stop_condition_file.parent),
        )
    stop = load_json(stop_condition_path)

    meaning_synthesis_file = Path(meaning_synthesis_path)
    if not meaning_synthesis_file.exists():
        build_v161_meaning_synthesis(
            v160_closeout_path=v160_closeout_path,
            out_dir=str(meaning_synthesis_file.parent),
        )
    synthesis = load_json(meaning_synthesis_path)

    stop_status = str(stop.get("phase_stop_condition_status") or "not_ready_for_closeout")
    explicit_caveat_present = bool(synthesis.get("explicit_caveat_present"))
    do_not_continue = bool(synthesis.get("do_not_continue_v0_16_same_next_change_question_loop_by_default"))
    next_q = str(synthesis.get("next_primary_phase_question") or NEXT_PRIMARY_PHASE_QUESTION)

    if stop_status == "met":
        version_decision = "v0_16_1_handoff_phase_inputs_invalid"
        v0_17_primary_phase_question = "met_path_not_yet_in_scope_for_v0_16_1"
        status = "FAIL"
        closeout_status = "V0_16_1_HANDOFF_PHASE_INPUTS_INVALID"
    elif stop_status == "nearly_complete_with_caveat" and explicit_caveat_present and do_not_continue:
        version_decision = "v0_16_phase_nearly_complete_with_explicit_caveat"
        v0_17_primary_phase_question = next_q
        status = "PASS"
        closeout_status = "V0_16_PHASE_NEARLY_COMPLETE_WITH_EXPLICIT_CAVEAT"
    elif stop_status == "not_ready_for_closeout":
        version_decision = "v0_16_phase_not_ready_for_closeout"
        v0_17_primary_phase_question = "resolve_v0_16_phase_incompleteness_first"
        status = "FAIL"
        closeout_status = "V0_16_PHASE_NOT_READY_FOR_CLOSEOUT"
    else:
        version_decision = "v0_16_1_handoff_phase_inputs_invalid"
        v0_17_primary_phase_question = "rebuild_v0_16_phase_inputs_first"
        status = "FAIL"
        closeout_status = "V0_16_1_HANDOFF_PHASE_INPUTS_INVALID"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": version_decision,
            "phase_stop_condition_status": stop_status,
            "explicit_caveat_present": synthesis.get("explicit_caveat_present"),
            "explicit_caveat_label": synthesis.get("explicit_caveat_label"),
            "next_primary_phase_question": next_q,
            "do_not_continue_v0_16_same_next_change_question_loop_by_default": do_not_continue,
            "why_v0_16_is_or_is_not_phase_complete": synthesis.get("why_this_phase_is_or_is_not_closeable"),
            "v0_17_primary_phase_question": v0_17_primary_phase_question,
        },
        "phase_ledger": ledger,
        "phase_stop_condition": stop,
        "meaning_synthesis": synthesis,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.16.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- phase_stop_condition_status: `{stop_status}`",
                f"- next_primary_phase_question: `{next_q}`",
                f"- v0_17_primary_phase_question: `{v0_17_primary_phase_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.16.1 phase synthesis closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-condition", default=str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"))
    parser.add_argument("--meaning-synthesis", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--v160-closeout", default=str(DEFAULT_V160_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v161_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_condition_path=str(args.stop_condition),
        meaning_synthesis_path=str(args.meaning_synthesis),
        v160_closeout_path=str(args.v160_closeout),
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
