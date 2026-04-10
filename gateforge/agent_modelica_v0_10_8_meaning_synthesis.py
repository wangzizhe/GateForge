from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_8_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V106_CLOSEOUT_PATH,
    DEFAULT_V107_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v108_meaning_synthesis(
    *,
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    v107_closeout_path: str = str(DEFAULT_V107_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    v106 = load_json(v106_closeout_path)
    v107 = load_json(v107_closeout_path)
    c106 = v106.get("conclusion") or {}
    c107 = v107.get("conclusion") or {}

    explicit_caveat_present = (
        str(c106.get("final_adjudication_label") or "") == "real_origin_workflow_readiness_partial_but_interpretable"
    )
    explicit_caveat_label = (
        "real_origin_workflow_readiness_remains_partial_rather_than_supported_even_after_real_origin_source_shift"
        if explicit_caveat_present
        else ""
    )
    phase_status = "nearly_complete" if explicit_caveat_present else "complete"
    why_non_blocking = (
        "The caveat is non-blocking because the real-origin workflow result is formally adjudicated, remains explainable under the frozen real-origin chain, and one more bounded real-origin step has already been explicitly ruled not worth another version."
        if explicit_caveat_present
        else "No explicit caveat remains."
    )

    next_primary_phase_question = "workflow_to_product_gap_evaluation"
    why_not_other = {
        "real_origin_to_product_transition_readiness": "Current v0.10.x established that the workflow picture remains trustworthy on real-origin evidence, but it still remains partial rather than supported, so the next tighter question is the workflow-to-product gap rather than a broader transition-readiness claim.",
        "reopen_bounded_real_origin_refinement": "v0.10.7 already concluded that one more bounded real-origin step would likely add only marginal information, so reopening the same refinement loop would contradict the frozen governance result.",
    }
    do_not_continue = str(c107.get("version_decision") or "") == "v0_10_7_more_bounded_real_origin_step_not_worth_it"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_meaning_synthesis",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "explicit_caveat_present": explicit_caveat_present,
        "explicit_caveat_label": explicit_caveat_label,
        "phase_status": phase_status,
        "why_the_caveat_is_or_is_not_non_blocking": why_non_blocking,
        "next_primary_phase_question": next_primary_phase_question,
        "why_not_the_other_candidates": why_not_other,
        "do_not_continue_v0_10_same_real_origin_refinement_by_default": do_not_continue,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.8 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{next_primary_phase_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.8 meaning synthesis artifact.")
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--v107-closeout", default=str(DEFAULT_V107_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v108_meaning_synthesis(
        v106_closeout_path=str(args.v106_closeout),
        v107_closeout_path=str(args.v107_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_primary_phase_question": payload.get("next_primary_phase_question")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
