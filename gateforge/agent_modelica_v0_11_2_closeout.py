from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_2_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR,
    DEFAULT_PRODUCT_GAP_SUBSTRATE_SIZE,
    DEFAULT_V103_SUBSTRATE_BUILDER_PATH,
    DEFAULT_V111_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_2_handoff_integrity import build_v112_handoff_integrity
from .agent_modelica_v0_11_2_product_gap_substrate_admission import build_v112_product_gap_substrate_admission
from .agent_modelica_v0_11_2_product_gap_substrate_builder import build_v112_product_gap_substrate_builder


def build_v112_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    product_gap_substrate_builder_path: str = str(DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"),
    product_gap_substrate_admission_path: str = str(DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"),
    v111_closeout_path: str = str(DEFAULT_V111_CLOSEOUT_PATH),
    v103_substrate_builder_path: str = str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    builder_path_obj = Path(product_gap_substrate_builder_path)
    admission_path_obj = Path(product_gap_substrate_admission_path)

    if not handoff_path_obj.exists():
        build_v112_handoff_integrity(
            v111_closeout_path=v111_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_11_2_PRODUCT_GAP_SUBSTRATE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_11_2_product_gap_substrate_inputs_invalid",
                "first_product_gap_substrate_status": "invalid",
                "why_this_is_or_is_not_ready": "The upstream v0.11.1 patch-pack handoff is no longer valid, so the first product-gap substrate cannot be frozen yet.",
                "v0_11_3_handoff_mode": "rebuild_v0_11_2_substrate_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.11.2 Closeout\n\n- version_decision: `v0_11_2_product_gap_substrate_inputs_invalid`\n")
        return payload

    if not builder_path_obj.exists():
        build_v112_product_gap_substrate_builder(
            v103_substrate_builder_path=v103_substrate_builder_path,
            out_dir=str(builder_path_obj.parent),
        )
    builder = load_json(product_gap_substrate_builder_path)

    if not admission_path_obj.exists():
        build_v112_product_gap_substrate_admission(
            product_gap_substrate_builder_path=product_gap_substrate_builder_path,
            v103_substrate_builder_path=v103_substrate_builder_path,
            out_dir=str(admission_path_obj.parent),
        )
    admission = load_json(product_gap_substrate_admission_path)

    admission_status = str(admission.get("product_gap_substrate_admission_status") or "invalid")
    size = int(admission.get("product_gap_substrate_size") or 0)
    same_substrate_continuity_pass = bool(admission.get("same_substrate_continuity_pass"))
    instrumentation_completeness_pass = bool(admission.get("instrumentation_completeness_pass"))
    traceability_pass = bool(admission.get("traceability_pass"))
    default_same_substrate_rule_used = bool(builder.get("default_same_substrate_rule_used"))
    derivative_used = bool(builder.get("derivative_used"))

    if (
        admission_status == "ready"
        and size == DEFAULT_PRODUCT_GAP_SUBSTRATE_SIZE
        and same_substrate_continuity_pass
        and instrumentation_completeness_pass
        and traceability_pass
        and default_same_substrate_rule_used
        and not derivative_used
    ):
        version_decision = "v0_11_2_first_product_gap_substrate_ready"
        substrate_status = "ready"
        handoff_mode = "characterize_first_product_gap_profile"
        status = "PASS"
        why = "The first product-gap substrate now preserves the exact carried 12-case baseline with governed row-level instrumentation and traceability."
    elif (
        admission_status != "invalid"
        and same_substrate_continuity_pass
        and traceability_pass
        and (
            not instrumentation_completeness_pass
            or admission_status == "partial"
            or derivative_used
        )
    ):
        version_decision = "v0_11_2_first_product_gap_substrate_partial"
        substrate_status = "partial"
        handoff_mode = "finish_product_gap_substrate_freeze_first"
        status = "PASS"
        why = "The first product-gap substrate direction is valid and traceable, but it is still derivative or missing some preferred same-substrate instrumentation completeness."
    else:
        version_decision = "v0_11_2_product_gap_substrate_inputs_invalid"
        substrate_status = "invalid"
        handoff_mode = "rebuild_v0_11_2_substrate_inputs_first"
        status = "FAIL"
        why = "The builder or admission artifact breaks the derivative rule, same-substrate contract, or traceability discipline required for the first product-gap substrate."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "first_product_gap_substrate_status": substrate_status,
            "why_this_is_or_is_not_ready": why,
            "v0_11_3_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "product_gap_substrate_builder": builder,
        "product_gap_substrate_admission": admission,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- first_product_gap_substrate_status: `{substrate_status}`",
                f"- v0_11_3_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.2 closeout artifact.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--product-gap-substrate-builder", default=str(DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"))
    parser.add_argument("--product-gap-substrate-admission", default=str(DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--v111-closeout", default=str(DEFAULT_V111_CLOSEOUT_PATH))
    parser.add_argument("--v103-substrate-builder", default=str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v112_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        product_gap_substrate_builder_path=str(args.product_gap_substrate_builder),
        product_gap_substrate_admission_path=str(args.product_gap_substrate_admission),
        v111_closeout_path=str(args.v111_closeout),
        v103_substrate_builder_path=str(args.v103_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
