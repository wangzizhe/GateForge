from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_3_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V121_CLOSEOUT_PATH,
    DEFAULT_V122_CLOSEOUT_PATH,
    EXPECTED_V121_VERSION_DECISION,
    EXPECTED_V122_VERSION_DECISION,
    EXPLICIT_CAVEAT_LABEL,
    NEXT_PRIMARY_PHASE_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v123_meaning_synthesis(
    *,
    v121_closeout_path: str = str(DEFAULT_V121_CLOSEOUT_PATH),
    v122_closeout_path: str = str(DEFAULT_V122_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    c121 = (load_json(v121_closeout_path).get("conclusion") or {})
    c122 = (load_json(v122_closeout_path).get("conclusion") or {})

    first_pack_non_material = str(c121.get("version_decision") or "") == EXPECTED_V121_VERSION_DECISION
    stronger_not_in_scope = str(c122.get("version_decision") or "") == EXPECTED_V122_VERSION_DECISION

    # The caveat is present when the operational remedy route was evaluated and found non-material
    # with no stronger bounded remedy remaining in scope.
    explicit_caveat_present = first_pack_non_material and stronger_not_in_scope
    explicit_caveat_label = EXPLICIT_CAVEAT_LABEL if explicit_caveat_present else ""

    # Hard rule: explicit_caveat_present = true → do_not_continue must also be true
    do_not_continue = explicit_caveat_present

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_meaning_synthesis",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "meaning_synthesis_status": "interpreted",
        "explicit_caveat_present": explicit_caveat_present,
        "explicit_caveat_label": explicit_caveat_label,
        "phase_level_readout": (
            "The v0.12.x operational-remedy evaluation route was executed honestly: "
            "governance was frozen, the first bounded pack was evaluated through real same-source "
            "live pre/post comparison and found non-material, and stronger bounded operational remedies "
            "were adjudicated as not in scope. The carried blocker points toward capability-level "
            "improvement rather than further shell-level hardening."
            if explicit_caveat_present
            else "Operational remedy chain incomplete; phase level meaning cannot be fully stated."
        ),
        "next_primary_phase_question": NEXT_PRIMARY_PHASE_QUESTION,
        "do_not_continue_v0_12_same_operational_remedy_refinement_by_default": do_not_continue,
        "why_this_phase_is_or_is_not_closeable": (
            "The caveat is non-blocking because the operational-remedy chain is now "
            "governance-backed, first-pack-executed, same-source-compared, and "
            "stronger-remedy-scope-adjudicated. Both primary questions of the v0.12.x phase "
            "have been answered with real evidence."
            if explicit_caveat_present
            else "Phase cannot close; primary questions not yet answered with real evidence."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.3 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{NEXT_PRIMARY_PHASE_QUESTION}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.3 meaning synthesis artifact.")
    parser.add_argument("--v121-closeout", default=str(DEFAULT_V121_CLOSEOUT_PATH))
    parser.add_argument("--v122-closeout", default=str(DEFAULT_V122_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v123_meaning_synthesis(
        v121_closeout_path=str(args.v121_closeout),
        v122_closeout_path=str(args.v122_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "next_primary_phase_question": payload.get("next_primary_phase_question"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
