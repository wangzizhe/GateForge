from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_14_3_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V141_CLOSEOUT_PATH,
    DEFAULT_V142_CLOSEOUT_PATH,
    EXPECTED_V141_VERSION_DECISIONS,
    EXPECTED_V142_VERSION_DECISION,
    EXPLICIT_CAVEAT_LABEL,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v143_meaning_synthesis(
    *,
    v141_closeout_path: str = str(DEFAULT_V141_CLOSEOUT_PATH),
    v142_closeout_path: str = str(DEFAULT_V142_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    c141 = load_json(v141_closeout_path).get("conclusion") or {}
    c142 = load_json(v142_closeout_path).get("conclusion") or {}

    first_pack_effect_answered = str(c141.get("version_decision") or "") in EXPECTED_V141_VERSION_DECISIONS
    first_pack_effect_class = str(c141.get("broader_change_effect_class") or "")
    stronger_not_in_scope = str(c142.get("version_decision") or "") == EXPECTED_V142_VERSION_DECISION

    explicit_caveat_present = first_pack_effect_answered and stronger_not_in_scope
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
            "The v0.14.x broader-change route was evaluated honestly: governance was frozen, the first broader-change "
            "pack was executed through same-source live pre/post comparison and produced only a non-material or "
            "side-evidence-only effect, and stronger governed broader-change escalation was adjudicated as not in "
            "scope. The carried picture therefore points beyond same-class broader-change refinement toward an even "
            "broader change question."
            if explicit_caveat_present
            else "Broader-change chain incomplete; phase-level meaning cannot yet be stated cleanly."
        ),
        "next_primary_phase_question": NEXT_PRIMARY_PHASE_QUESTION,
        "do_not_continue_v0_14_same_broader_change_refinement_by_default": do_not_continue,
        "why_this_phase_is_or_is_not_closeable": (
            "The caveat is non-blocking because the broader-change route is now governance-backed, first-pack-executed, "
            "and stronger-scope-adjudicated. The phase answered the broader-change question honestly without materially "
            "rewriting the carried picture."
            if explicit_caveat_present
            else "Phase cannot close; broader-change questions are not yet fully answered."
        ),
        "carried_first_pack_effect_class": first_pack_effect_class,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.3 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{NEXT_PRIMARY_PHASE_QUESTION}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.3 meaning synthesis artifact.")
    parser.add_argument("--v141-closeout", default=str(DEFAULT_V141_CLOSEOUT_PATH))
    parser.add_argument("--v142-closeout", default=str(DEFAULT_V142_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v143_meaning_synthesis(
        v141_closeout_path=str(args.v141_closeout),
        v142_closeout_path=str(args.v142_closeout),
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
