from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_17_1_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V170_CLOSEOUT_PATH,
    EXPECTED_V170_GOVERNANCE_OUTCOME,
    EXPECTED_V170_VERSION_DECISION,
    EXPLICIT_CAVEAT_LABEL,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v171_meaning_synthesis(
    *,
    v170_closeout_path: str = str(DEFAULT_V170_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    c170 = load_json(v170_closeout_path).get("conclusion") or {}

    governance_answered = str(c170.get("version_decision") or "") == EXPECTED_V170_VERSION_DECISION
    no_honest_answered = str(c170.get("transition_governance_outcome") or "") == EXPECTED_V170_GOVERNANCE_OUTCOME

    explicit_caveat_present = governance_answered and no_honest_answered
    explicit_caveat_label = EXPLICIT_CAVEAT_LABEL if explicit_caveat_present else ""
    do_not_continue = explicit_caveat_present

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_meaning_synthesis",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "meaning_synthesis_status": "interpreted",
        "explicit_caveat_present": explicit_caveat_present,
        "explicit_caveat_label": explicit_caveat_label,
        "phase_level_readout": (
            "The v0.17.x carried-baseline-evidence-exhaustion branch was evaluated honestly: the project reopened governance one "
            "level above local-question exhaustion, explicitly allowed the possibility that no honest transition question remained, "
            "and the carried result was exactly that no such governed transition question remained on the same 12-case baseline. "
            "The carried picture therefore points beyond governed transition-question evaluation toward the next honest move problem."
            if explicit_caveat_present
            else "v0.17.x transition governance chain incomplete; phase-level meaning cannot yet be stated cleanly."
        ),
        "next_primary_phase_question": NEXT_PRIMARY_PHASE_QUESTION,
        "do_not_continue_v0_17_same_transition_question_loop_by_default": do_not_continue,
        "why_this_phase_is_or_is_not_closeable": (
            "The caveat is non-blocking because the branch already made the relevant transition-governance question explicit and "
            "answered it: no further honest governed transition question remained on the carried baseline."
            if explicit_caveat_present
            else "Phase cannot close; the transition-governance question has not yet been answered cleanly enough."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.17.1 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{NEXT_PRIMARY_PHASE_QUESTION}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.17.1 meaning synthesis artifact.")
    parser.add_argument("--v170-closeout", default=str(DEFAULT_V170_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v171_meaning_synthesis(
        v170_closeout_path=str(args.v170_closeout),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "next_primary_phase_question": payload.get("next_primary_phase_question"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
