from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_16_1_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V160_CLOSEOUT_PATH,
    EXPECTED_V160_GOVERNANCE_OUTCOME,
    EXPECTED_V160_VERSION_DECISION,
    EXPLICIT_CAVEAT_LABEL,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v161_meaning_synthesis(
    *,
    v160_closeout_path: str = str(DEFAULT_V160_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    c160 = load_json(v160_closeout_path).get("conclusion") or {}

    governance_answered = str(c160.get("version_decision") or "") == EXPECTED_V160_VERSION_DECISION
    no_honest_answered = str(c160.get("next_change_governance_outcome") or "") == EXPECTED_V160_GOVERNANCE_OUTCOME

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
            "The v0.16.x post-even-broader branch was evaluated honestly: the project reopened governance one more time, "
            "explicitly allowed the possibility that no further honest local next-change question remained, and the carried "
            "result was exactly that no such local governed question remained on the same 12-case baseline. The carried picture "
            "therefore points beyond same-class local change governance toward an evidence-exhaustion or evaluation-object transition question."
            if explicit_caveat_present
            else "v0.16.x next-change governance chain incomplete; phase-level meaning cannot yet be stated cleanly."
        ),
        "next_primary_phase_question": NEXT_PRIMARY_PHASE_QUESTION,
        "do_not_continue_v0_16_same_next_change_question_loop_by_default": do_not_continue,
        "why_this_phase_is_or_is_not_closeable": (
            "The caveat is non-blocking because the branch already made the relevant governance question explicit and answered it: "
            "no further honest local next-change question remained on the carried baseline."
            if explicit_caveat_present
            else "Phase cannot close; the next-change governance question has not yet been answered cleanly enough."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.16.1 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{NEXT_PRIMARY_PHASE_QUESTION}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.16.1 meaning synthesis artifact.")
    parser.add_argument("--v160-closeout", default=str(DEFAULT_V160_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v161_meaning_synthesis(
        v160_closeout_path=str(args.v160_closeout),
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
