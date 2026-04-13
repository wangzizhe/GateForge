from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_13_3_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V131_CLOSEOUT_PATH,
    DEFAULT_V132_CLOSEOUT_PATH,
    EXPECTED_V131_VERSION_DECISION,
    EXPECTED_V132_VERSION_DECISION,
    EXPLICIT_CAVEAT_LABEL,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v133_meaning_synthesis(
    *,
    v131_closeout_path: str = str(DEFAULT_V131_CLOSEOUT_PATH),
    v132_closeout_path: str = str(DEFAULT_V132_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    c131 = load_json(v131_closeout_path).get("conclusion") or {}
    c132 = load_json(v132_closeout_path).get("conclusion") or {}

    first_pack_side_evidence_only = str(c131.get("version_decision") or "") == EXPECTED_V131_VERSION_DECISION
    stronger_not_in_scope = str(c132.get("version_decision") or "") == EXPECTED_V132_VERSION_DECISION

    explicit_caveat_present = first_pack_side_evidence_only and stronger_not_in_scope
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
            "The v0.13.x bounded capability-intervention route was evaluated honestly: "
            "governance was frozen, the first bounded pack was executed through same-source live "
            "pre/post comparison and produced only side evidence, and stronger bounded capability "
            "intervention escalation was adjudicated as not in scope. The carried picture therefore "
            "points beyond same-class bounded intervention refinement toward a broader change question."
            if explicit_caveat_present
            else "Capability-intervention chain incomplete; phase-level meaning cannot yet be stated cleanly."
        ),
        "next_primary_phase_question": NEXT_PRIMARY_PHASE_QUESTION,
        "do_not_continue_v0_13_same_capability_intervention_refinement_by_default": do_not_continue,
        "why_this_phase_is_or_is_not_closeable": (
            "The caveat is non-blocking because the bounded capability-intervention route is now "
            "governance-backed, first-pack-executed, and stronger-scope-adjudicated. The phase answered "
            "the bounded capability question honestly without materially changing the carried picture."
            if explicit_caveat_present
            else "Phase cannot close; bounded capability-intervention questions are not yet fully answered."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.3 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{NEXT_PRIMARY_PHASE_QUESTION}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.3 meaning synthesis artifact.")
    parser.add_argument("--v131-closeout", default=str(DEFAULT_V131_CLOSEOUT_PATH))
    parser.add_argument("--v132-closeout", default=str(DEFAULT_V132_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v133_meaning_synthesis(
        v131_closeout_path=str(args.v131_closeout),
        v132_closeout_path=str(args.v132_closeout),
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
