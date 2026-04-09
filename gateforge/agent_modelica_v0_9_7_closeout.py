from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_7_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V090_CLOSEOUT_PATH,
    DEFAULT_V091_CLOSEOUT_PATH,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_CLOSEOUT_PATH,
    DEFAULT_V095_CLOSEOUT_PATH,
    DEFAULT_V096_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_7_meaning_synthesis import build_v097_meaning_synthesis
from .agent_modelica_v0_9_7_phase_ledger import build_v097_phase_ledger
from .agent_modelica_v0_9_7_stop_condition import build_v097_stop_condition


def build_v097_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_condition_path: str = str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"),
    meaning_synthesis_path: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"),
    v090_closeout_path: str = str(DEFAULT_V090_CLOSEOUT_PATH),
    v091_closeout_path: str = str(DEFAULT_V091_CLOSEOUT_PATH),
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    v095_closeout_path: str = str(DEFAULT_V095_CLOSEOUT_PATH),
    v096_closeout_path: str = str(DEFAULT_V096_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    build_v097_phase_ledger(
        v090_closeout_path=v090_closeout_path,
        v091_closeout_path=v091_closeout_path,
        v092_closeout_path=v092_closeout_path,
        v093_closeout_path=v093_closeout_path,
        v094_closeout_path=v094_closeout_path,
        v095_closeout_path=v095_closeout_path,
        v096_closeout_path=v096_closeout_path,
        out_dir=str(Path(phase_ledger_path).parent),
    )
    ledger = load_json(phase_ledger_path)
    if ledger.get("phase_ledger_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_7_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_7_handoff_phase_inputs_invalid",
                "phase_status": "invalid",
                "next_phase_handoff_mode": "rebuild_v0_9_phase_inputs_first",
                "do_not_continue_v0_9_same_authentic_expansion_by_default": True,
            },
            "phase_ledger": ledger,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.7 Closeout\n\n- version_decision: `v0_9_7_handoff_phase_inputs_invalid`\n")
        return payload

    build_v097_stop_condition(
        v090_closeout_path=v090_closeout_path,
        v091_closeout_path=v091_closeout_path,
        v092_closeout_path=v092_closeout_path,
        v093_closeout_path=v093_closeout_path,
        v094_closeout_path=v094_closeout_path,
        v095_closeout_path=v095_closeout_path,
        v096_closeout_path=v096_closeout_path,
        out_dir=str(Path(stop_condition_path).parent),
    )
    stop = load_json(stop_condition_path)

    build_v097_meaning_synthesis(
        v095_closeout_path=v095_closeout_path,
        v096_closeout_path=v096_closeout_path,
        out_dir=str(Path(meaning_synthesis_path).parent),
    )
    synthesis = load_json(meaning_synthesis_path)

    stop_status = str(stop.get("phase_stop_condition_status") or "not_ready_for_closeout")
    explicit_caveat_present = bool(synthesis.get("explicit_caveat_present"))
    do_not_continue = bool(synthesis.get("do_not_continue_v0_9_same_authentic_expansion_by_default"))
    why_non_blocking = str(synthesis.get("why_the_caveat_is_or_is_not_non_blocking") or "")

    if stop_status in {"met", "nearly_complete_with_caveat"} and explicit_caveat_present and do_not_continue:
        version_decision = "v0_9_phase_nearly_complete_with_explicit_caveat"
        phase_status = "nearly_complete"
        next_phase_handoff_mode = "start_next_phase_with_explicit_v0_9_caveat"
        status = "PASS"
    elif stop_status == "not_ready_for_closeout":
        version_decision = "v0_9_phase_not_ready_for_closeout"
        phase_status = "not_complete"
        next_phase_handoff_mode = "repair_v0_9_phase_closure_gaps_first"
        status = "FAIL"
    else:
        version_decision = "v0_9_7_handoff_phase_inputs_invalid"
        phase_status = "invalid"
        next_phase_handoff_mode = "rebuild_v0_9_phase_inputs_first"
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
            "do_not_continue_v0_9_same_authentic_expansion_by_default": do_not_continue,
            "why_v0_9_is_or_is_not_phase_complete": why_non_blocking,
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
                "# v0.9.7 Closeout",
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
    parser = argparse.ArgumentParser(description="Build the v0.9.7 phase synthesis closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-condition", default=str(DEFAULT_STOP_CONDITION_OUT_DIR / "summary.json"))
    parser.add_argument("--meaning-synthesis", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--v090-closeout", default=str(DEFAULT_V090_CLOSEOUT_PATH))
    parser.add_argument("--v091-closeout", default=str(DEFAULT_V091_CLOSEOUT_PATH))
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--v095-closeout", default=str(DEFAULT_V095_CLOSEOUT_PATH))
    parser.add_argument("--v096-closeout", default=str(DEFAULT_V096_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v097_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_condition_path=str(args.stop_condition),
        meaning_synthesis_path=str(args.meaning_synthesis),
        v090_closeout_path=str(args.v090_closeout),
        v091_closeout_path=str(args.v091_closeout),
        v092_closeout_path=str(args.v092_closeout),
        v093_closeout_path=str(args.v093_closeout),
        v094_closeout_path=str(args.v094_closeout),
        v095_closeout_path=str(args.v095_closeout),
        v096_closeout_path=str(args.v096_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
