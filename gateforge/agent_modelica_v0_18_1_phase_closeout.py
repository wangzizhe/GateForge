from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_18_1_common import (
    DEFAULT_PHASE_CLOSEOUT_OUT_DIR,
    EXPLICIT_CAVEAT_LABEL,
    NEXT_PRIMARY_PHASE_QUESTION,
    PHASE_STOP_CONDITION_STATUS,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)


def build_v181_phase_closeout(
    *,
    closeout_needed: bool = True,
    out_dir: str = str(DEFAULT_PHASE_CLOSEOUT_OUT_DIR),
) -> dict:
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "phase_closeout_decision_status": "ready",
        "closeout_needed": bool(closeout_needed),
        "named_reason_if_closeout_not_needed": (
            "v0_18_0_already_closed_the_honest_next_move_question_substantively_under_compressed_versioning"
        ),
        "phase_stop_condition_status": PHASE_STOP_CONDITION_STATUS,
        "explicit_caveat_present": True,
        "explicit_caveat_label": EXPLICIT_CAVEAT_LABEL,
        "next_primary_phase_question": NEXT_PRIMARY_PHASE_QUESTION,
        "phase_level_readout_status": "ready",
        "phase_question": "post_transition_question_exhaustion_next_honest_move",
        "phase_answer": "the_carried_evidence_boundary_now_supports_no_honest_next_move_beyond_the_existing_governed_frontier",
        "carried_evidence_boundary_reading": (
            "the_project_has_reached_the_edge_of_honest_next_move_generation_on_the_same_carried_12_case_baseline"
        ),
        "do_not_continue_v0_18_same_next_move_loop_by_default": True,
        "why_v0_18_is_or_is_not_phase_complete": (
            "The phase already answered the honest-next-move question substantively in v0.18.0; this closeout either emits the "
            "standard carried-chain label or explicitly records that no extra thin closeout artifact was needed."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.18.1 Phase Closeout",
                "",
                f"- closeout_needed: `{payload['closeout_needed']}`",
                f"- phase_stop_condition_status: `{payload['phase_stop_condition_status']}`",
                f"- next_primary_phase_question: `{payload['next_primary_phase_question']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.18.1 phase-closeout artifact.")
    parser.add_argument("--closeout-needed", choices=["true", "false"], default="true")
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v181_phase_closeout(closeout_needed=args.closeout_needed == "true", out_dir=str(args.out_dir))
    print(json.dumps({"status": payload["status"], "closeout_needed": payload["closeout_needed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
