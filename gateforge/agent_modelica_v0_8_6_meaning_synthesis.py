from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_6_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V084_CLOSEOUT_PATH,
    DEFAULT_V085_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v086_meaning_synthesis(
    *,
    v084_closeout_path: str = str(DEFAULT_V084_CLOSEOUT_PATH),
    v085_closeout_path: str = str(DEFAULT_V085_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    v084 = load_json(v084_closeout_path)
    v085 = load_json(v085_closeout_path)
    c084 = v084.get("conclusion") or {}
    c085 = v085.get("conclusion") or {}

    explicit_caveat_present = c084.get("adjudication_route") == "workflow_readiness_partial_but_interpretable"
    explicit_caveat_label = (
        "workflow_readiness_remains_partial_rather_than_supported_on_frozen_workflow_proximal_substrate"
        if explicit_caveat_present
        else ""
    )
    why_non_blocking = (
        "The caveat is non-blocking because the workflow result is formally adjudicated, remains interpretable, and same-logic refinement has already been explicitly ruled not worth another version."
        if explicit_caveat_present
        else "No explicit caveat remains."
    )

    v0_9_primary_phase_question = "authenticity_constrained_barrier_aware_workflow_expansion"
    why_not_other = {
        "workflow_to_product_gap_evaluation": "Current v0.8.x only established a stable partial workflow-proximal result, not a product-proximal base strong enough to make workflow-to-product gap evaluation the next mainline.",
        "real_origin_workflow_readiness_evaluation": "A real-origin workflow phase would be premature before expanding barrier coverage under authenticity constraints on the current workflow-proximal frame.",
    }

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_meaning_synthesis",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "explicit_caveat_present": explicit_caveat_present,
        "explicit_caveat_label": explicit_caveat_label,
        "why_the_caveat_is_or_is_not_non_blocking": why_non_blocking,
        "v0_9_primary_phase_question": v0_9_primary_phase_question,
        "why_not_the_other_candidates": why_not_other,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.6 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- v0_9_primary_phase_question: `{v0_9_primary_phase_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.6 meaning synthesis artifact.")
    parser.add_argument("--v084-closeout", default=str(DEFAULT_V084_CLOSEOUT_PATH))
    parser.add_argument("--v085-closeout", default=str(DEFAULT_V085_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v086_meaning_synthesis(
        v084_closeout_path=str(args.v084_closeout),
        v085_closeout_path=str(args.v085_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_9_primary_phase_question": payload.get("v0_9_primary_phase_question")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
