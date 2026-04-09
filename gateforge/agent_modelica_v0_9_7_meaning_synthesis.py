from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_7_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V095_CLOSEOUT_PATH,
    DEFAULT_V096_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v097_meaning_synthesis(
    *,
    v095_closeout_path: str = str(DEFAULT_V095_CLOSEOUT_PATH),
    v096_closeout_path: str = str(DEFAULT_V096_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    v095 = load_json(v095_closeout_path)
    v096 = load_json(v096_closeout_path)
    c095 = v095.get("conclusion") or {}
    c096 = v096.get("conclusion") or {}

    explicit_caveat_present = (
        str(c095.get("final_adjudication_label") or "") == "expanded_workflow_readiness_partial_but_interpretable"
    )
    explicit_caveat_label = (
        "expanded_workflow_readiness_remains_partial_rather_than_supported_even_after_authenticity_constrained_barrier_aware_expansion"
        if explicit_caveat_present
        else ""
    )
    why_non_blocking = (
        "The caveat is non-blocking because the expanded workflow result is formally adjudicated, remains fully explainable under the frozen authentic-expansion chain, and one more bounded authentic expansion has already been explicitly ruled not worth another version."
        if explicit_caveat_present
        else "No explicit caveat remains."
    )

    next_primary_phase_question = "real_origin_workflow_readiness_evaluation"
    why_not_other = {
        "workflow_to_product_gap_evaluation": "Current v0.9.x established a trustworthy authenticity-constrained workflow expansion picture, but it did not yet produce the stronger real-origin workflow evidence that should precede product-gap evaluation.",
        "reopen_authenticity_constrained_barrier_aware_workflow_expansion": "v0.9.6 already concluded that one more bounded authentic expansion would likely add only marginal information, so reopening the same phase question would contradict the frozen governance result.",
    }
    do_not_continue = (
        str(c096.get("version_decision") or "") == "v0_9_6_more_authentic_expansion_not_worth_it"
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_meaning_synthesis",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "explicit_caveat_present": explicit_caveat_present,
        "explicit_caveat_label": explicit_caveat_label,
        "why_the_caveat_is_or_is_not_non_blocking": why_non_blocking,
        "next_primary_phase_question": next_primary_phase_question,
        "why_not_the_other_candidates": why_not_other,
        "do_not_continue_v0_9_same_authentic_expansion_by_default": do_not_continue,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.7 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{next_primary_phase_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.7 meaning synthesis artifact.")
    parser.add_argument("--v095-closeout", default=str(DEFAULT_V095_CLOSEOUT_PATH))
    parser.add_argument("--v096-closeout", default=str(DEFAULT_V096_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v097_meaning_synthesis(
        v095_closeout_path=str(args.v095_closeout),
        v096_closeout_path=str(args.v096_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_primary_phase_question": payload.get("next_primary_phase_question")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
