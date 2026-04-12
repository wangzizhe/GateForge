from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_3_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V120_CLOSEOUT_PATH,
    DEFAULT_V121_CLOSEOUT_PATH,
    DEFAULT_V122_CLOSEOUT_PATH,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_12_3_meaning_synthesis import build_v123_meaning_synthesis
from .agent_modelica_v0_12_3_phase_ledger import build_v123_phase_ledger
from .agent_modelica_v0_12_3_stop_condition import build_v123_stop_condition


def build_v123_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_condition_path: str = str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"),
    meaning_synthesis_path: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"),
    v120_closeout_path: str = str(DEFAULT_V120_CLOSEOUT_PATH),
    v121_closeout_path: str = str(DEFAULT_V121_CLOSEOUT_PATH),
    v122_closeout_path: str = str(DEFAULT_V122_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    phase_ledger_file = Path(phase_ledger_path)
    if not phase_ledger_file.exists():
        build_v123_phase_ledger(
            v120_closeout_path=v120_closeout_path,
            v121_closeout_path=v121_closeout_path,
            v122_closeout_path=v122_closeout_path,
            out_dir=str(phase_ledger_file.parent),
        )
    ledger = load_json(phase_ledger_path)

    if ledger.get("phase_ledger_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_12_3_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_12_3_handoff_phase_inputs_invalid",
                "v0_13_primary_phase_question": "rebuild_v0_12_phase_inputs_first",
            },
            "phase_ledger": ledger,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.12.3 Closeout\n\n- version_decision: `v0_12_3_handoff_phase_inputs_invalid`\n")
        return payload

    stop_condition_file = Path(stop_condition_path)
    if not stop_condition_file.exists():
        build_v123_stop_condition(
            v120_closeout_path=v120_closeout_path,
            v121_closeout_path=v121_closeout_path,
            v122_closeout_path=v122_closeout_path,
            out_dir=str(stop_condition_file.parent),
        )
    stop = load_json(stop_condition_path)

    meaning_synthesis_file = Path(meaning_synthesis_path)
    if not meaning_synthesis_file.exists():
        build_v123_meaning_synthesis(
            v121_closeout_path=v121_closeout_path,
            v122_closeout_path=v122_closeout_path,
            out_dir=str(meaning_synthesis_file.parent),
        )
    synthesis = load_json(meaning_synthesis_path)

    stop_status = str(stop.get("phase_stop_condition_status") or "not_ready_for_closeout")
    explicit_caveat_present = bool(synthesis.get("explicit_caveat_present"))
    do_not_continue = bool(synthesis.get("do_not_continue_v0_12_same_operational_remedy_refinement_by_default"))
    next_q = str(synthesis.get("next_primary_phase_question") or NEXT_PRIMARY_PHASE_QUESTION)

    # Route table (plan § Step 4)
    if stop_status == "met":
        # met is future-reserved for v0.12.3
        version_decision = "v0_12_3_handoff_phase_inputs_invalid"
        v0_13_primary_phase_question = "met_path_not_yet_in_scope_for_v0_12_3"
        status = "FAIL"
        closeout_status = "V0_12_3_HANDOFF_PHASE_INPUTS_INVALID"
    elif stop_status == "nearly_complete_with_caveat" and explicit_caveat_present and do_not_continue:
        version_decision = "v0_12_phase_nearly_complete_with_explicit_caveat"
        v0_13_primary_phase_question = next_q
        status = "PASS"
        closeout_status = "V0_12_PHASE_NEARLY_COMPLETE_WITH_EXPLICIT_CAVEAT"
    elif stop_status == "not_ready_for_closeout":
        version_decision = "v0_12_phase_not_ready_for_closeout"
        v0_13_primary_phase_question = "resolve_v0_12_phase_incompleteness_first"
        status = "FAIL"
        closeout_status = "V0_12_PHASE_NOT_READY_FOR_CLOSEOUT"
    else:
        version_decision = "v0_12_3_handoff_phase_inputs_invalid"
        v0_13_primary_phase_question = "rebuild_v0_12_phase_inputs_first"
        status = "FAIL"
        closeout_status = "V0_12_3_HANDOFF_PHASE_INPUTS_INVALID"

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
            "do_not_continue_v0_12_same_operational_remedy_refinement_by_default": do_not_continue,
            "why_v0_12_is_or_is_not_phase_complete": synthesis.get("why_this_phase_is_or_is_not_closeable"),
            "v0_13_primary_phase_question": v0_13_primary_phase_question,
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
                "# v0.12.3 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- phase_stop_condition_status: `{stop_status}`",
                f"- next_primary_phase_question: `{next_q}`",
                f"- v0_13_primary_phase_question: `{v0_13_primary_phase_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.3 phase synthesis closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-condition", default=str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"))
    parser.add_argument("--meaning-synthesis", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--v120-closeout", default=str(DEFAULT_V120_CLOSEOUT_PATH))
    parser.add_argument("--v121-closeout", default=str(DEFAULT_V121_CLOSEOUT_PATH))
    parser.add_argument("--v122-closeout", default=str(DEFAULT_V122_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v123_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_condition_path=str(args.stop_condition),
        meaning_synthesis_path=str(args.meaning_synthesis),
        v120_closeout_path=str(args.v120_closeout),
        v121_closeout_path=str(args.v121_closeout),
        v122_closeout_path=str(args.v122_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "version_decision": (payload.get("conclusion") or {}).get("version_decision"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
