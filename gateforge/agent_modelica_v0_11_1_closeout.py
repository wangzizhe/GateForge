from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_1_bounded_validation_pack import build_v111_bounded_validation_pack
from .agent_modelica_v0_11_1_common import (
    DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR,
    DEFAULT_V103_SUBSTRATE_BUILDER_PATH,
    DEFAULT_V110_CLOSEOUT_PATH,
    DEFAULT_V110_GOVERNANCE_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_1_handoff_integrity import build_v111_handoff_integrity
from .agent_modelica_v0_11_1_patch_pack_execution import build_v111_patch_pack_execution


def build_v111_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    patch_pack_execution_path: str = str(DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR / "summary.json"),
    bounded_validation_pack_path: str = str(DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR / "summary.json"),
    v110_closeout_path: str = str(DEFAULT_V110_CLOSEOUT_PATH),
    v110_governance_pack_path: str = str(DEFAULT_V110_GOVERNANCE_PACK_PATH),
    v103_substrate_builder_path: str = str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    patch_path_obj = Path(patch_pack_execution_path)
    validation_path_obj = Path(bounded_validation_pack_path)

    if not handoff_path_obj.exists():
        build_v111_handoff_integrity(
            v110_closeout_path=v110_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_11_1_PATCH_PACK_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_11_1_patch_pack_inputs_invalid",
                "first_product_gap_patch_pack_status": "invalid",
                "why_this_is_or_is_not_ready": "The upstream v0.11.0 governance handoff is no longer valid, so bounded patch-pack execution cannot be trusted.",
                "v0_11_2_handoff_mode": "rebuild_v0_11_1_patch_pack_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.11.1 Closeout\n\n- version_decision: `v0_11_1_patch_pack_inputs_invalid`\n")
        return payload

    if not patch_path_obj.exists():
        build_v111_patch_pack_execution(
            v110_governance_pack_path=v110_governance_pack_path,
            out_dir=str(patch_path_obj.parent),
        )
    patch_pack = load_json(patch_pack_execution_path)

    if not validation_path_obj.exists():
        build_v111_bounded_validation_pack(
            v103_substrate_builder_path=v103_substrate_builder_path,
            out_dir=str(validation_path_obj.parent),
        )
    validation = load_json(bounded_validation_pack_path)

    patch_status = str(patch_pack.get("patch_pack_execution_status") or "invalid")
    validation_status = str(validation.get("validation_pack_status") or "invalid")
    one_to_one_traceability_pass = bool(validation.get("one_to_one_traceability_pass"))
    required_sidecar_fields_emitted = bool(validation.get("required_sidecar_fields_emitted"))
    profile_level_claim_made = bool(validation.get("profile_level_claim_made"))
    bounded_validation_only = bool(validation.get("bounded_validation_only"))
    non_regression_pass = bool(validation.get("non_regression_pass"))

    if (
        patch_status == "ready"
        and validation_status == "ready"
        and one_to_one_traceability_pass
        and required_sidecar_fields_emitted
        and not profile_level_claim_made
        and bounded_validation_only
        and non_regression_pass
    ):
        version_decision = "v0_11_1_first_product_gap_patch_pack_ready"
        pack_status = "ready"
        handoff_mode = "freeze_first_product_gap_evaluation_substrate"
        status = "PASS"
        why = "The governed patch pack is now operational, the bounded carried-baseline validation pack emits the required side evidence, and the next version can freeze the first product-gap substrate."
    elif (
        patch_status != "invalid"
        and validation_status != "invalid"
        and (
            patch_status == "partial"
            or validation_status == "partial"
            or not required_sidecar_fields_emitted
        )
    ):
        version_decision = "v0_11_1_first_product_gap_patch_pack_partial"
        pack_status = "partial"
        handoff_mode = "finish_patch_pack_or_sidecar_observability_first"
        status = "PASS"
        why = "The bounded patch direction is valid, but at least one patch row or required side-evidence field remains incomplete."
    else:
        version_decision = "v0_11_1_patch_pack_inputs_invalid"
        pack_status = "invalid"
        handoff_mode = "rebuild_v0_11_1_patch_pack_inputs_first"
        status = "FAIL"
        why = "The patch-pack execution or bounded validation pack is invalid, so the first product-gap substrate should not proceed yet."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "first_product_gap_patch_pack_status": pack_status,
            "why_this_is_or_is_not_ready": why,
            "v0_11_2_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "patch_pack_execution": patch_pack,
        "bounded_validation_pack": validation,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- first_product_gap_patch_pack_status: `{pack_status}`",
                f"- v0_11_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.1 closeout artifact.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--patch-pack-execution", default=str(DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR / "summary.json"))
    parser.add_argument("--bounded-validation-pack", default=str(DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v110-closeout", default=str(DEFAULT_V110_CLOSEOUT_PATH))
    parser.add_argument("--v110-governance-pack", default=str(DEFAULT_V110_GOVERNANCE_PACK_PATH))
    parser.add_argument("--v103-substrate-builder", default=str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v111_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        patch_pack_execution_path=str(args.patch_pack_execution),
        bounded_validation_pack_path=str(args.bounded_validation_pack),
        v110_closeout_path=str(args.v110_closeout),
        v110_governance_pack_path=str(args.v110_governance_pack),
        v103_substrate_builder_path=str(args.v103_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
