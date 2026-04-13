from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_15_2_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V150_CLOSEOUT_PATH,
    DEFAULT_V151_CLOSEOUT_PATH,
    EXPECTED_V150_VERSION_DECISION,
    EXPECTED_V151_VERSION_DECISION,
    EXPLICIT_CAVEAT_LABEL,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v152_meaning_synthesis(
    *,
    v150_closeout_path: str = str(DEFAULT_V150_CLOSEOUT_PATH),
    v151_closeout_path: str = str(DEFAULT_V151_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    c150 = load_json(v150_closeout_path).get("conclusion") or {}
    c151 = load_json(v151_closeout_path).get("conclusion") or {}

    governance_answered = str(c150.get("version_decision") or "") == EXPECTED_V150_VERSION_DECISION
    viability_answered = str(c151.get("version_decision") or "") == EXPECTED_V151_VERSION_DECISION

    explicit_caveat_present = governance_answered and viability_answered
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
            "The v0.15.x even-broader-change route was evaluated honestly: governance was frozen, the project explicitly "
            "reassessed whether an even-broader execution arc should open, and the result remained not justified on the carried "
            "same-source baseline. The carried picture therefore points beyond same-class even-broader refinement toward a still "
            "later change question."
            if explicit_caveat_present
            else "Even-broader-change chain incomplete; phase-level meaning cannot yet be stated cleanly."
        ),
        "next_primary_phase_question": NEXT_PRIMARY_PHASE_QUESTION,
        "do_not_continue_v0_15_same_even_broader_refinement_by_default": do_not_continue,
        "why_this_phase_is_or_is_not_closeable": (
            "The caveat is non-blocking because the even-broader route is now governance-backed and viability-adjudicated. "
            "The phase answered whether opening the next execution arc was honest enough, and the answer remained no."
            if explicit_caveat_present
            else "Phase cannot close; the even-broader governance or viability question is not yet fully answered."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.15.2 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{NEXT_PRIMARY_PHASE_QUESTION}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.2 meaning synthesis artifact.")
    parser.add_argument("--v150-closeout", default=str(DEFAULT_V150_CLOSEOUT_PATH))
    parser.add_argument("--v151-closeout", default=str(DEFAULT_V151_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v152_meaning_synthesis(
        v150_closeout_path=str(args.v150_closeout),
        v151_closeout_path=str(args.v151_closeout),
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
