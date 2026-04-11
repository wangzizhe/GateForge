from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_7_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V116_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v117_meaning_synthesis(
    *,
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v116_closeout_path: str = str(DEFAULT_V116_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    c115 = (load_json(v115_closeout_path).get("conclusion") or {})
    c116 = (load_json(v116_closeout_path).get("conclusion") or {})

    explicit_caveat_present = (
        str(c115.get("formal_adjudication_label") or "") == "product_gap_partial_but_interpretable"
    )
    explicit_caveat_label = (
        "product_gap_remains_partial_rather_than_product_ready_after_governed_workflow_to_product_evaluation"
        if explicit_caveat_present
        else ""
    )
    next_primary_phase_question = "workflow_to_product_gap_operational_remedy_evaluation"
    do_not_continue = str(c116.get("version_decision") or "") == "v0_11_6_more_bounded_product_gap_step_not_worth_it"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_meaning_synthesis",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "phase_meaning_status": "interpreted",
        "explicit_caveat_present": explicit_caveat_present,
        "explicit_caveat_label": explicit_caveat_label,
        "next_primary_phase_question": next_primary_phase_question,
        "do_not_continue_v0_11_same_product_gap_refinement_by_default": do_not_continue,
        "why_this_phase_is_or_is_not_closeable": (
            "The caveat is non-blocking because the product-gap chain is now governance-backed, substrate-frozen, profile-characterized, threshold-frozen, formally adjudicated, and one more bounded product-gap step has already been ruled not worth another version."
            if explicit_caveat_present
            else "No explicit caveat remains."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.7 Meaning Synthesis",
                "",
                f"- explicit_caveat_present: `{explicit_caveat_present}`",
                f"- next_primary_phase_question: `{next_primary_phase_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.7 meaning synthesis artifact.")
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v116-closeout", default=str(DEFAULT_V116_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v117_meaning_synthesis(
        v115_closeout_path=str(args.v115_closeout),
        v116_closeout_path=str(args.v116_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_primary_phase_question": payload.get("next_primary_phase_question")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
