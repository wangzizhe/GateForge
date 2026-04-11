from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_2_common import (
    DEFAULT_CARRIED_BASELINE_SOURCE,
    DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_PRODUCT_GAP_SUBSTRATE_SIZE,
    DEFAULT_V103_SUBSTRATE_BUILDER_PATH,
    PATCH_PACK_OBSERVATION_FIELD_NAMES,
    PENDING_PROFILE_RUN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_2_product_gap_substrate_builder import build_v112_product_gap_substrate_builder


def _row_has_complete_instrumentation(row: dict) -> bool:
    observation_fields = row.get("patch_pack_carried_observation_fields")
    if not isinstance(observation_fields, dict):
        return False
    required_keys_present = all(key in observation_fields for key in PATCH_PACK_OBSERVATION_FIELD_NAMES)
    placeholder_values_valid = all(
        observation_fields.get(key) in (None, PENDING_PROFILE_RUN)
        for key in PATCH_PACK_OBSERVATION_FIELD_NAMES
    )
    static_fields_present = all(
        bool(row.get(field))
        for field in [
            "product_gap_scaffold_version",
            "product_gap_protocol_contract_version",
            "product_gap_context_contract_version",
            "product_gap_anti_reward_hacking_checklist_version",
        ]
    )
    return bool(required_keys_present and placeholder_values_valid and static_fields_present)


def build_v112_product_gap_substrate_admission(
    *,
    product_gap_substrate_builder_path: str,
    v103_substrate_builder_path: str = str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    builder_path_obj = Path(product_gap_substrate_builder_path)
    if not builder_path_obj.exists():
        build_v112_product_gap_substrate_builder(
            v103_substrate_builder_path=v103_substrate_builder_path,
            out_dir=str(builder_path_obj.parent),
        )

    builder = load_json(product_gap_substrate_builder_path)
    rows = builder.get("product_gap_candidate_table") if isinstance(builder.get("product_gap_candidate_table"), list) else []
    size = int(builder.get("product_gap_candidate_count") or len(rows))
    derivative_used = bool(builder.get("derivative_used"))
    derivative_rule_status = str(builder.get("derivative_rule_status") or "invalid")
    default_same_substrate_rule_used = bool(builder.get("default_same_substrate_rule_used"))
    silent_resampling_attempted = bool(builder.get("silent_resampling_attempted"))
    dynamic_prompt_audit_resolved = bool(builder.get("dynamic_prompt_audit_resolved"))

    carried_baseline_source_ok = builder.get("carried_baseline_source") == DEFAULT_CARRIED_BASELINE_SOURCE
    row_traceability_ok = all(bool(row.get("carried_from_v0_10_3")) for row in rows)
    same_substrate_continuity_pass = bool(
        carried_baseline_source_ok
        and (
            (not derivative_used and default_same_substrate_rule_used and size == DEFAULT_PRODUCT_GAP_SUBSTRATE_SIZE)
            or (derivative_used and derivative_rule_status == "ready")
        )
    )
    instrumentation_completeness_pass = bool(rows) and all(_row_has_complete_instrumentation(row) for row in rows)
    traceability_pass = bool(
        rows
        and row_traceability_ok
        and not silent_resampling_attempted
        and (
            (not derivative_used and default_same_substrate_rule_used)
            or (derivative_used and derivative_rule_status == "ready")
        )
    )
    dynamic_prompt_field_audit_state = (
        "explicit_and_stable" if dynamic_prompt_audit_resolved else "explicit_and_still_open"
    )
    carried_shell_observation_note = (
        "The dynamic prompt-field audit remains explicit at substrate-freeze time, but it is still a carried shell observation rather than a solved product-gap claim."
        if not dynamic_prompt_audit_resolved
        else "The builder carries explicit new evidence that the dynamic prompt-field audit is stable under the current substrate-freeze semantics."
    )

    if derivative_rule_status == "invalid" or not traceability_pass:
        admission_status = "invalid"
        why = "The first product-gap substrate breaks the derivative rule or loses carried-baseline traceability."
    elif derivative_used or not instrumentation_completeness_pass or not same_substrate_continuity_pass:
        admission_status = "partial"
        why = "The substrate direction is still governed and traceable, but same-substrate continuity or instrumentation completeness is weaker than the preferred ready path."
    else:
        admission_status = "ready"
        why = "The first product-gap substrate preserves the carried 12-case baseline and every admitted row now carries the governed product-boundary instrumentation schema."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_product_gap_substrate_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admission_status != "invalid" else "FAIL",
        "product_gap_substrate_admission_status": admission_status,
        "product_gap_substrate_size": size,
        "same_substrate_continuity_pass": same_substrate_continuity_pass,
        "instrumentation_completeness_pass": instrumentation_completeness_pass,
        "traceability_pass": traceability_pass,
        "dynamic_prompt_field_audit_state": dynamic_prompt_field_audit_state,
        "carried_shell_observation_note": carried_shell_observation_note,
        "why_this_is_or_is_not_valid": why,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.2 Product-Gap Substrate Admission",
                "",
                f"- product_gap_substrate_admission_status: `{admission_status}`",
                f"- product_gap_substrate_size: `{size}`",
                f"- same_substrate_continuity_pass: `{same_substrate_continuity_pass}`",
                f"- instrumentation_completeness_pass: `{instrumentation_completeness_pass}`",
                f"- traceability_pass: `{traceability_pass}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.2 product-gap substrate admission artifact.")
    parser.add_argument("--product-gap-substrate-builder", default="")
    parser.add_argument("--v103-substrate-builder", default=str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR))
    args = parser.parse_args()
    builder_path = (
        str(args.product_gap_substrate_builder)
        if str(args.product_gap_substrate_builder)
        else str(Path(args.out_dir).parent / "agent_modelica_v0_11_2_product_gap_substrate_builder_current" / "summary.json")
    )
    payload = build_v112_product_gap_substrate_admission(
        product_gap_substrate_builder_path=builder_path,
        v103_substrate_builder_path=str(args.v103_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "product_gap_substrate_admission_status": payload.get("product_gap_substrate_admission_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
