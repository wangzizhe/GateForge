from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_8_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V100_CLOSEOUT_PATH,
    DEFAULT_V101_CLOSEOUT_PATH,
    DEFAULT_V102_CLOSEOUT_PATH,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V105_CLOSEOUT_PATH,
    DEFAULT_V106_CLOSEOUT_PATH,
    DEFAULT_V107_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_8_meaning_synthesis import build_v108_meaning_synthesis
from .agent_modelica_v0_10_8_phase_ledger import build_v108_phase_ledger
from .agent_modelica_v0_10_8_stop_condition import build_v108_stop_condition


def build_v108_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_condition_path: str = str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"),
    meaning_synthesis_path: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"),
    v100_closeout_path: str = str(DEFAULT_V100_CLOSEOUT_PATH),
    v101_closeout_path: str = str(DEFAULT_V101_CLOSEOUT_PATH),
    v102_closeout_path: str = str(DEFAULT_V102_CLOSEOUT_PATH),
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    v105_closeout_path: str = str(DEFAULT_V105_CLOSEOUT_PATH),
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    v107_closeout_path: str = str(DEFAULT_V107_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    build_v108_phase_ledger(
        v100_closeout_path=v100_closeout_path,
        v101_closeout_path=v101_closeout_path,
        v102_closeout_path=v102_closeout_path,
        v103_closeout_path=v103_closeout_path,
        v104_closeout_path=v104_closeout_path,
        v105_closeout_path=v105_closeout_path,
        v106_closeout_path=v106_closeout_path,
        v107_closeout_path=v107_closeout_path,
        out_dir=str(Path(phase_ledger_path).parent),
    )
    ledger = load_json(phase_ledger_path)
    if ledger.get("phase_ledger_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_10_8_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_10_8_handoff_phase_inputs_invalid",
                "phase_status": "invalid",
                "next_phase_handoff_mode": "rebuild_v0_10_phase_inputs_first",
                "do_not_continue_v0_10_same_real_origin_refinement_by_default": True,
            },
            "phase_ledger": ledger,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.10.8 Closeout\n\n- version_decision: `v0_10_8_handoff_phase_inputs_invalid`\n")
        return payload

    build_v108_stop_condition(
        v100_closeout_path=v100_closeout_path,
        v101_closeout_path=v101_closeout_path,
        v102_closeout_path=v102_closeout_path,
        v103_closeout_path=v103_closeout_path,
        v104_closeout_path=v104_closeout_path,
        v105_closeout_path=v105_closeout_path,
        v106_closeout_path=v106_closeout_path,
        v107_closeout_path=v107_closeout_path,
        out_dir=str(Path(stop_condition_path).parent),
    )
    stop = load_json(stop_condition_path)

    build_v108_meaning_synthesis(
        v106_closeout_path=v106_closeout_path,
        v107_closeout_path=v107_closeout_path,
        out_dir=str(Path(meaning_synthesis_path).parent),
    )
    synthesis = load_json(meaning_synthesis_path)

    stop_status = str(stop.get("phase_stop_condition_status") or "not_ready_for_closeout")
    explicit_caveat_present = bool(synthesis.get("explicit_caveat_present"))
    do_not_continue = bool(synthesis.get("do_not_continue_v0_10_same_real_origin_refinement_by_default"))
    why_non_blocking = str(synthesis.get("why_the_caveat_is_or_is_not_non_blocking") or "")

    if stop_status in {"met", "nearly_complete_with_caveat"} and explicit_caveat_present and do_not_continue:
        version_decision = "v0_10_phase_nearly_complete_with_explicit_caveat"
        phase_status = "nearly_complete"
        next_phase_handoff_mode = "prepare_next_phase_from_v0_10_synthesis"
        status = "PASS"
    elif stop_status == "not_ready_for_closeout":
        version_decision = "v0_10_phase_not_ready_for_closeout"
        phase_status = "not_complete"
        next_phase_handoff_mode = "repair_v0_10_phase_stop_conditions_first"
        status = "FAIL"
    else:
        version_decision = "v0_10_8_handoff_phase_inputs_invalid"
        phase_status = "invalid"
        next_phase_handoff_mode = "rebuild_v0_10_phase_inputs_first"
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
            "next_primary_phase_question": synthesis.get("next_primary_phase_question"),
            "do_not_continue_v0_10_same_real_origin_refinement_by_default": do_not_continue,
            "why_v0_10_is_or_is_not_phase_complete": why_non_blocking,
            "next_phase_handoff_mode": next_phase_handoff_mode,
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
                "# v0.10.8 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- phase_status: `{phase_status}`",
                f"- phase_stop_condition_status: `{stop_status}`",
                f"- next_primary_phase_question: `{synthesis.get('next_primary_phase_question')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.8 phase synthesis closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-condition", default=str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"))
    parser.add_argument("--meaning-synthesis", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--v100-closeout", default=str(DEFAULT_V100_CLOSEOUT_PATH))
    parser.add_argument("--v101-closeout", default=str(DEFAULT_V101_CLOSEOUT_PATH))
    parser.add_argument("--v102-closeout", default=str(DEFAULT_V102_CLOSEOUT_PATH))
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--v105-closeout", default=str(DEFAULT_V105_CLOSEOUT_PATH))
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--v107-closeout", default=str(DEFAULT_V107_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v108_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_condition_path=str(args.stop_condition),
        meaning_synthesis_path=str(args.meaning_synthesis),
        v100_closeout_path=str(args.v100_closeout),
        v101_closeout_path=str(args.v101_closeout),
        v102_closeout_path=str(args.v102_closeout),
        v103_closeout_path=str(args.v103_closeout),
        v104_closeout_path=str(args.v104_closeout),
        v105_closeout_path=str(args.v105_closeout),
        v106_closeout_path=str(args.v106_closeout),
        v107_closeout_path=str(args.v107_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
