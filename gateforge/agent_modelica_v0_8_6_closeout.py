from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_6_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V080_CLOSEOUT_PATH,
    DEFAULT_V081_CLOSEOUT_PATH,
    DEFAULT_V082_CLOSEOUT_PATH,
    DEFAULT_V083_CLOSEOUT_PATH,
    DEFAULT_V084_CLOSEOUT_PATH,
    DEFAULT_V085_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_6_meaning_synthesis import build_v086_meaning_synthesis
from .agent_modelica_v0_8_6_phase_ledger import build_v086_phase_ledger
from .agent_modelica_v0_8_6_stop_condition import build_v086_stop_condition


def build_v086_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_condition_path: str = str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"),
    meaning_synthesis_path: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"),
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    v082_closeout_path: str = str(DEFAULT_V082_CLOSEOUT_PATH),
    v083_closeout_path: str = str(DEFAULT_V083_CLOSEOUT_PATH),
    v084_closeout_path: str = str(DEFAULT_V084_CLOSEOUT_PATH),
    v085_closeout_path: str = str(DEFAULT_V085_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    build_v086_phase_ledger(
        v080_closeout_path=v080_closeout_path,
        v081_closeout_path=v081_closeout_path,
        v082_closeout_path=v082_closeout_path,
        v083_closeout_path=v083_closeout_path,
        v084_closeout_path=v084_closeout_path,
        v085_closeout_path=v085_closeout_path,
        out_dir=str(Path(phase_ledger_path).parent),
    )
    ledger = load_json(phase_ledger_path)
    if ledger.get("phase_ledger_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_8_6_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_8_6_handoff_phase_inputs_invalid",
                "phase_status": "invalid",
                "v0_9_handoff_mode": "rebuild_v0_8_phase_inputs_first",
                "do_not_continue_v0_8_same_logic_refinement_by_default": True,
            },
            "phase_ledger": ledger,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.8.6 Closeout\n\n- version_decision: `v0_8_6_handoff_phase_inputs_invalid`\n")
        return payload

    build_v086_stop_condition(
        v080_closeout_path=v080_closeout_path,
        v081_closeout_path=v081_closeout_path,
        v082_closeout_path=v082_closeout_path,
        v083_closeout_path=v083_closeout_path,
        v084_closeout_path=v084_closeout_path,
        v085_closeout_path=v085_closeout_path,
        out_dir=str(Path(stop_condition_path).parent),
    )
    stop = load_json(stop_condition_path)

    build_v086_meaning_synthesis(
        v084_closeout_path=v084_closeout_path,
        v085_closeout_path=v085_closeout_path,
        out_dir=str(Path(meaning_synthesis_path).parent),
    )
    synthesis = load_json(meaning_synthesis_path)

    stop_status = str(stop.get("phase_stop_condition_status") or "not_ready_for_closeout")
    if stop_status in {"met", "nearly_complete_with_caveat"} and bool(synthesis.get("explicit_caveat_present")):
        version_decision = "v0_8_phase_nearly_complete_with_explicit_caveat"
        phase_status = "nearly_complete"
        handoff_mode = "start_next_phase_with_explicit_v0_8_caveat"
        status = "PASS"
    elif stop_status == "not_ready_for_closeout":
        version_decision = "v0_8_phase_not_ready_for_closeout"
        phase_status = "not_ready"
        handoff_mode = "repair_v0_8_phase_closure_gaps_first"
        status = "FAIL"
    else:
        version_decision = "v0_8_phase_not_ready_for_closeout"
        phase_status = "not_ready"
        handoff_mode = "repair_v0_8_phase_closure_gaps_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "phase_status": phase_status,
            "phase_stop_condition_status": stop_status,
            "explicit_caveat_present": synthesis.get("explicit_caveat_present"),
            "explicit_caveat_label": synthesis.get("explicit_caveat_label"),
            "v0_9_primary_phase_question": synthesis.get("v0_9_primary_phase_question"),
            "do_not_continue_v0_8_same_logic_refinement_by_default": True,
            "why_v0_8_is_or_is_not_phase_complete": synthesis.get("why_the_caveat_is_or_is_not_non_blocking"),
            "v0_9_handoff_mode": handoff_mode,
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
                "# v0.8.6 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- phase_status: `{phase_status}`",
                f"- phase_stop_condition_status: `{stop_status}`",
                f"- v0_9_primary_phase_question: `{synthesis.get('v0_9_primary_phase_question')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.6 phase synthesis closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-condition", default=str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"))
    parser.add_argument("--meaning-synthesis", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--v080-closeout", default=str(DEFAULT_V080_CLOSEOUT_PATH))
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--v082-closeout", default=str(DEFAULT_V082_CLOSEOUT_PATH))
    parser.add_argument("--v083-closeout", default=str(DEFAULT_V083_CLOSEOUT_PATH))
    parser.add_argument("--v084-closeout", default=str(DEFAULT_V084_CLOSEOUT_PATH))
    parser.add_argument("--v085-closeout", default=str(DEFAULT_V085_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v086_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_condition_path=str(args.stop_condition),
        meaning_synthesis_path=str(args.meaning_synthesis),
        v080_closeout_path=str(args.v080_closeout),
        v081_closeout_path=str(args.v081_closeout),
        v082_closeout_path=str(args.v082_closeout),
        v083_closeout_path=str(args.v083_closeout),
        v084_closeout_path=str(args.v084_closeout),
        v085_closeout_path=str(args.v085_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
