from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_5_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    DEFAULT_V113_CLOSEOUT_PATH,
    DEFAULT_V114_CLOSEOUT_PATH,
    DEFAULT_V114_THRESHOLD_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_5_first_product_gap_adjudication import build_v115_first_product_gap_adjudication
from .agent_modelica_v0_11_5_handoff_integrity import build_v115_handoff_integrity
from .agent_modelica_v0_11_5_product_gap_adjudication_input_table import (
    build_v115_product_gap_adjudication_input_table,
)


def build_v115_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    product_gap_adjudication_input_table_path: str = str(
        DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"
    ),
    first_product_gap_adjudication_path: str = str(DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR / "summary.json"),
    v114_closeout_path: str = str(DEFAULT_V114_CLOSEOUT_PATH),
    v114_threshold_pack_path: str = str(DEFAULT_V114_THRESHOLD_PACK_PATH),
    v113_closeout_path: str = str(DEFAULT_V113_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v115_handoff_integrity(
        v114_closeout_path=v114_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_11_5_PRODUCT_GAP_ADJUDICATION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_11_5_product_gap_adjudication_inputs_invalid",
                "v0_11_6_handoff_mode": "rebuild_product_gap_adjudication_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "# v0.11.5 Closeout\n\n- version_decision: `v0_11_5_product_gap_adjudication_inputs_invalid`\n",
        )
        return payload

    if not Path(product_gap_adjudication_input_table_path).exists():
        build_v115_product_gap_adjudication_input_table(
            v114_closeout_path=v114_closeout_path,
            v114_threshold_pack_path=v114_threshold_pack_path,
            v113_closeout_path=v113_closeout_path,
            out_dir=str(Path(product_gap_adjudication_input_table_path).parent),
        )
    if not Path(first_product_gap_adjudication_path).exists():
        build_v115_first_product_gap_adjudication(
            product_gap_adjudication_input_table_path=product_gap_adjudication_input_table_path,
            out_dir=str(Path(first_product_gap_adjudication_path).parent),
        )

    adjudication_input = load_json(product_gap_adjudication_input_table_path)
    adjudication = load_json(first_product_gap_adjudication_path)

    route_count = int(adjudication.get("adjudication_route_count") or 0)
    route = str(adjudication.get("final_adjudication_label") or "")
    posture_ok = bool(adjudication.get("execution_posture_semantics_preserved"))

    if route_count != 1 or not posture_ok:
        decision = "v0_11_5_product_gap_adjudication_inputs_invalid"
        handoff = "rebuild_product_gap_adjudication_inputs_first"
        status = "FAIL"
        closeout_status = "V0_11_5_PRODUCT_GAP_ADJUDICATION_INPUTS_INVALID"
    elif route == "product_gap_supported":
        decision = "v0_11_5_first_product_gap_profile_supported"
        handoff = "decide_whether_phase_synthesis_is_already_justified"
        status = "PASS"
        closeout_status = "V0_11_5_FIRST_PRODUCT_GAP_PROFILE_SUPPORTED"
    elif route == "product_gap_partial_but_interpretable":
        decision = "v0_11_5_first_product_gap_profile_partial_but_interpretable"
        handoff = "decide_whether_one_more_bounded_product_gap_step_is_still_worth_it"
        status = "PASS"
        closeout_status = "V0_11_5_FIRST_PRODUCT_GAP_PROFILE_PARTIAL_BUT_INTERPRETABLE"
    elif route == "product_gap_fallback":
        decision = "v0_11_5_first_product_gap_profile_fallback_to_profile_clarification_needed"
        handoff = "decide_whether_profile_clarification_or_gap_frame_reset_is_needed"
        status = "PASS"
        closeout_status = "V0_11_5_FIRST_PRODUCT_GAP_PROFILE_FALLBACK_TO_PROFILE_CLARIFICATION_NEEDED"
    else:
        decision = "v0_11_5_product_gap_adjudication_inputs_invalid"
        handoff = "rebuild_product_gap_adjudication_inputs_first"
        status = "FAIL"
        closeout_status = "V0_11_5_PRODUCT_GAP_ADJUDICATION_INPUTS_INVALID"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": decision,
            "formal_adjudication_label": route,
            "supported_check_pass": adjudication.get("supported_check_pass"),
            "partial_check_pass": adjudication.get("partial_check_pass"),
            "fallback_triggered": adjudication.get("fallback_triggered"),
            "execution_posture_semantics_preserved": posture_ok,
            "dominant_gap_family_readout": adjudication.get("dominant_gap_family_readout"),
            "adjudication_explanation": adjudication.get("adjudication_explanation"),
            "v0_11_6_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "product_gap_adjudication_input_table": adjudication_input,
        "first_product_gap_adjudication": adjudication,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.5 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- formal_adjudication_label: `{route}`",
                f"- dominant_gap_family_readout: `{adjudication.get('dominant_gap_family_readout')}`",
                f"- v0_11_6_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.5 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--product-gap-adjudication-input-table",
        default=str(DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--first-product-gap-adjudication",
        default=str(DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v114-closeout", default=str(DEFAULT_V114_CLOSEOUT_PATH))
    parser.add_argument("--v114-threshold-pack", default=str(DEFAULT_V114_THRESHOLD_PACK_PATH))
    parser.add_argument("--v113-closeout", default=str(DEFAULT_V113_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v115_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        product_gap_adjudication_input_table_path=str(args.product_gap_adjudication_input_table),
        first_product_gap_adjudication_path=str(args.first_product_gap_adjudication),
        v114_closeout_path=str(args.v114_closeout),
        v114_threshold_pack_path=str(args.v114_threshold_pack),
        v113_closeout_path=str(args.v113_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
