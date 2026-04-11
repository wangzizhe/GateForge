from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_11_2_common import (
    ALLOWED_DERIVATIVE_REASONS,
    ANTI_REWARD_HACKING_CHECKLIST_VERSION,
    CONTEXT_CONTRACT_VERSION,
    CURRENT_PROTOCOL_CONTRACT_VERSION,
    DEFAULT_CARRIED_BASELINE_SOURCE,
    DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR,
    DEFAULT_PRODUCT_GAP_SUBSTRATE_KIND,
    DEFAULT_V103_SUBSTRATE_BUILDER_PATH,
    PATCH_PACK_OBSERVATION_FIELD_NAMES,
    PENDING_PROFILE_RUN,
    SCHEMA_PREFIX,
    SCAFFOLD_VERSION,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _placeholder_patch_pack_fields() -> dict:
    return {field: PENDING_PROFILE_RUN for field in PATCH_PACK_OBSERVATION_FIELD_NAMES}


def _instrument_row(row: dict) -> dict:
    return {
        **copy.deepcopy(row),
        "carried_from_v0_10_3": True,
        "product_gap_scaffold_version": SCAFFOLD_VERSION,
        "product_gap_protocol_contract_version": CURRENT_PROTOCOL_CONTRACT_VERSION,
        "product_gap_context_contract_version": CONTEXT_CONTRACT_VERSION,
        "product_gap_anti_reward_hacking_checklist_version": ANTI_REWARD_HACKING_CHECKLIST_VERSION,
        "patch_pack_carried_observation_fields": _placeholder_patch_pack_fields(),
        "product_gap_row_admission_pass": True,
    }


def build_v112_product_gap_substrate_builder(
    *,
    v103_substrate_builder_path: str = str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH),
    derivative_used: bool = False,
    named_product_boundary_reason: str = "",
    removed_case_ids: list[str] | None = None,
    added_case_rows: list[dict] | None = None,
    one_to_one_traceability_exceptions: list[str] | None = None,
    dynamic_prompt_audit_resolved: bool = False,
    out_dir: str = str(DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v103_substrate_builder_path)
    base_rows = (
        upstream.get("real_origin_substrate_candidate_table")
        if isinstance(upstream.get("real_origin_substrate_candidate_table"), list)
        else []
    )
    removed_case_ids = list(removed_case_ids or [])
    added_case_rows = list(added_case_rows or [])
    one_to_one_traceability_exceptions = list(one_to_one_traceability_exceptions or [])

    removed_set = set(removed_case_ids)
    base_task_ids = [str(row.get("task_id") or "") for row in base_rows]
    missing_removed_case_ids = [task_id for task_id in removed_case_ids if task_id not in base_task_ids]
    silent_resampling_attempted = bool(added_case_rows)
    invalid_named_reason = bool(derivative_used and named_product_boundary_reason not in ALLOWED_DERIVATIVE_REASONS)

    candidate_rows = [
        _instrument_row(row)
        for row in base_rows
        if str(row.get("task_id") or "") not in removed_set
    ]

    derivative_rule_status = "not_used"
    if derivative_used:
        if invalid_named_reason or missing_removed_case_ids or silent_resampling_attempted:
            derivative_rule_status = "invalid"
        else:
            derivative_rule_status = "ready"

    status = "PASS"
    if derivative_rule_status == "invalid":
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_product_gap_substrate_builder",
        "generated_at_utc": now_utc(),
        "status": status,
        "product_gap_substrate_kind": DEFAULT_PRODUCT_GAP_SUBSTRATE_KIND,
        "carried_baseline_source": DEFAULT_CARRIED_BASELINE_SOURCE,
        "default_same_substrate_rule_used": not derivative_used,
        "product_gap_candidate_count": len(candidate_rows),
        "product_gap_candidate_table": candidate_rows,
        "derivative_used": derivative_used,
        "named_product_boundary_reason": named_product_boundary_reason if derivative_used else "",
        "removed_case_ids": removed_case_ids if derivative_used else [],
        "added_case_ids": [str(row.get("task_id") or "") for row in added_case_rows] if derivative_used else [],
        "one_to_one_traceability_exceptions": one_to_one_traceability_exceptions if derivative_used else [],
        "derivative_rule_status": derivative_rule_status,
        "missing_removed_case_ids": missing_removed_case_ids,
        "silent_resampling_attempted": silent_resampling_attempted,
        "dynamic_prompt_audit_resolved": bool(dynamic_prompt_audit_resolved),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.2 Product-Gap Substrate Builder",
                "",
                f"- product_gap_candidate_count: `{payload['product_gap_candidate_count']}`",
                f"- derivative_used: `{payload['derivative_used']}`",
                f"- derivative_rule_status: `{payload['derivative_rule_status']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.2 product-gap substrate builder artifact.")
    parser.add_argument("--v103-substrate-builder", default=str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--derivative-used", action="store_true")
    parser.add_argument("--named-product-boundary-reason", default="")
    parser.add_argument("--removed-case-id", action="append", default=[])
    parser.add_argument("--dynamic-prompt-audit-resolved", action="store_true")
    parser.add_argument("--out-dir", default=str(DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v112_product_gap_substrate_builder(
        v103_substrate_builder_path=str(args.v103_substrate_builder),
        derivative_used=bool(args.derivative_used),
        named_product_boundary_reason=str(args.named_product_boundary_reason),
        removed_case_ids=list(args.removed_case_id),
        dynamic_prompt_audit_resolved=bool(args.dynamic_prompt_audit_resolved),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "product_gap_candidate_count": payload.get("product_gap_candidate_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
