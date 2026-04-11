from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_7_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V110_CLOSEOUT_PATH,
    DEFAULT_V111_CLOSEOUT_PATH,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V113_CLOSEOUT_PATH,
    DEFAULT_V114_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V116_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v117_stop_condition(
    *,
    v110_closeout_path: str = str(DEFAULT_V110_CLOSEOUT_PATH),
    v111_closeout_path: str = str(DEFAULT_V111_CLOSEOUT_PATH),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v113_closeout_path: str = str(DEFAULT_V113_CLOSEOUT_PATH),
    v114_closeout_path: str = str(DEFAULT_V114_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v116_closeout_path: str = str(DEFAULT_V116_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    c110 = (load_json(v110_closeout_path).get("conclusion") or {})
    c111 = (load_json(v111_closeout_path).get("conclusion") or {})
    c112 = (load_json(v112_closeout_path).get("conclusion") or {})
    c113 = (load_json(v113_closeout_path).get("conclusion") or {})
    c114 = (load_json(v114_closeout_path).get("conclusion") or {})
    c115 = (load_json(v115_closeout_path).get("conclusion") or {})
    c116 = (load_json(v116_closeout_path).get("conclusion") or {})

    governance_layer_frozen = c110.get("version_decision") == "v0_11_0_product_gap_governance_ready"
    first_patch_pack_executed_and_validated = c111.get("version_decision") == "v0_11_1_first_product_gap_patch_pack_ready"
    first_product_gap_substrate_frozen = c112.get("version_decision") == "v0_11_2_first_product_gap_substrate_ready"
    first_product_gap_profile_characterized = c113.get("version_decision") == "v0_11_3_first_product_gap_profile_characterized"
    first_product_gap_thresholds_frozen = c114.get("version_decision") == "v0_11_4_first_product_gap_thresholds_frozen"
    formal_adjudication_label = str(c115.get("formal_adjudication_label") or "")
    version_decision = str(c115.get("version_decision") or "")
    first_product_gap_adjudication_completed = (
        version_decision.startswith("v0_11_5_first_product_gap_profile_")
        and formal_adjudication_label in {"product_gap_partial_but_interpretable", "product_gap_supported"}
    )
    one_more_bounded_product_gap_step_not_worth_it = (
        c116.get("version_decision") == "v0_11_6_more_bounded_product_gap_step_not_worth_it"
        and c116.get("remaining_uncertainty_status") == "no_phase_relevant_uncertainty_remaining"
        and c116.get("expected_information_gain") == "marginal"
        and c116.get("proposed_next_step_kind") == "none"
    )

    dominant_gap_readout = str(c115.get("dominant_gap_family_readout") or "")
    dominant_gap_family_named_or_namedly_unresolved = dominant_gap_readout not in {"", "mixed_or_not_yet_resolved"}

    checks = {
        "governance_layer_frozen": governance_layer_frozen,
        "first_patch_pack_executed_and_validated": first_patch_pack_executed_and_validated,
        "first_product_gap_substrate_frozen": first_product_gap_substrate_frozen,
        "first_product_gap_profile_characterized": first_product_gap_profile_characterized,
        "first_product_gap_thresholds_frozen": first_product_gap_thresholds_frozen,
        "first_product_gap_adjudication_completed": first_product_gap_adjudication_completed,
        "one_more_bounded_product_gap_step_not_worth_it": one_more_bounded_product_gap_step_not_worth_it,
        "dominant_gap_family_named_or_namedly_unresolved": dominant_gap_family_named_or_namedly_unresolved,
    }

    base_seven = all(list(checks.values())[:7])
    final_is_supported = formal_adjudication_label == "product_gap_supported"
    final_is_partial = formal_adjudication_label == "product_gap_partial_but_interpretable"

    if base_seven and checks["dominant_gap_family_named_or_namedly_unresolved"] and final_is_supported:
        phase_stop_condition_status = "met"
    elif base_seven and checks["dominant_gap_family_named_or_namedly_unresolved"] and final_is_partial:
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status in {"met", "nearly_complete_with_caveat"} else "FAIL",
        "phase_stop_condition_status": phase_stop_condition_status,
        "phase_stop_condition_checks": checks,
        "explicit_caveat_needed": final_is_partial,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.7 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.7 stop condition artifact.")
    parser.add_argument("--v110-closeout", default=str(DEFAULT_V110_CLOSEOUT_PATH))
    parser.add_argument("--v111-closeout", default=str(DEFAULT_V111_CLOSEOUT_PATH))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v113-closeout", default=str(DEFAULT_V113_CLOSEOUT_PATH))
    parser.add_argument("--v114-closeout", default=str(DEFAULT_V114_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v116-closeout", default=str(DEFAULT_V116_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v117_stop_condition(
        v110_closeout_path=str(args.v110_closeout),
        v111_closeout_path=str(args.v111_closeout),
        v112_closeout_path=str(args.v112_closeout),
        v113_closeout_path=str(args.v113_closeout),
        v114_closeout_path=str(args.v114_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v116_closeout_path=str(args.v116_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_stop_condition_status": payload.get("phase_stop_condition_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
