"""Block E: Version Closeout for v0.6.0.

Aggregates Block A-D results and emits the final version_decision,
representative_authority_admission, primary_substrate_gap,
v0_6_1_handoff_mode, and do_not_revert_to_v0_5_boundary_pressure_by_default.
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any

from .agent_modelica_v0_6_0_common import (
    DEFAULT_AUTHORITY_ADMISSION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
    DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR,
    DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    DEFAULT_V057_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _derive_version_decision(admission: str) -> str:
    mapping = {
        "ready": "v0_6_0_representative_substrate_ready",
        "partial": "v0_6_0_representative_substrate_partial",
        "invalid": "v0_6_0_representative_substrate_invalid",
        "not_ready": "v0_6_0_representative_substrate_not_ready",
    }
    return mapping.get(admission, "v0_6_0_representative_substrate_invalid")


def _derive_handoff_mode(admission: str, gap: str) -> str:
    if admission == "ready":
        return "proceed_to_v0_6_1_authority_profile_characterization"
    if admission == "partial":
        return "fix_substrate_gap_before_v0_6_1_authority_profile"
    # invalid
    if gap == "dispatch_cleanliness_failed":
        return "repair_dispatch_attribution_before_v0_6_1"
    return "repair_representativeness_claim_before_v0_6_1"


def build_closeout(
    v057_closeout_path: Path = DEFAULT_V057_CLOSEOUT_PATH,
    substrate_dir: Path = DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    dispatch_dir: Path = DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
    classification_dir: Path = DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR,
    admission_dir: Path = DEFAULT_AUTHORITY_ADMISSION_OUT_DIR,
    out_dir: Path = DEFAULT_CLOSEOUT_OUT_DIR,
) -> dict[str, Any]:
    v057 = load_json(v057_closeout_path)
    substrate = load_json(substrate_dir / "summary.json")
    dispatch = load_json(dispatch_dir / "summary.json")
    classification = load_json(classification_dir / "summary.json")
    admission_data = load_json(admission_dir / "summary.json")

    admission = admission_data["representative_authority_admission"]
    gap = admission_data["primary_substrate_gap"]
    can_enter = admission_data["can_enter_broader_authority_profile"]
    version_decision = _derive_version_decision(admission)
    handoff_mode = _derive_handoff_mode(admission, gap)

    overall_status = "PASS" if admission in {"ready", "partial"} else "FAIL"

    result: dict[str, Any] = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": overall_status,
        "closeout_status": (
            "V0_6_0_REPRESENTATIVE_SUBSTRATE_READY"
            if admission == "ready"
            else (
                "V0_6_0_REPRESENTATIVE_SUBSTRATE_PARTIAL"
                if admission == "partial"
                else "V0_6_0_REPRESENTATIVE_SUBSTRATE_INVALID"
            )
        ),
        "conclusion": {
            "version_decision": version_decision,
            "representative_authority_admission": admission,
            "primary_substrate_gap": gap,
            "can_enter_broader_authority_profile": can_enter,
            "v0_6_1_handoff_mode": handoff_mode,
            "do_not_revert_to_v0_5_boundary_pressure_by_default": True,
        },
        "block_a_substrate": {
            "representative_slice_frozen": substrate.get("representative_slice_frozen"),
            "case_count": substrate.get("case_count"),
            "complexity_breakdown": substrate.get("complexity_breakdown"),
            "slice_class_breakdown": substrate.get("slice_class_breakdown"),
            "already_covered_pct": substrate.get("already_covered_pct"),
            "sampling_strategy_not_boundary_pressure_driven": substrate.get(
                "sampling_strategy_not_boundary_pressure_driven"
            ),
        },
        "block_b_dispatch": {
            "dispatch_cleanliness_level": dispatch.get("dispatch_cleanliness_level"),
            "attribution_ambiguity_rate_pct": dispatch.get("attribution_ambiguity_rate_pct"),
            "policy_baseline_valid": dispatch.get("policy_baseline_valid"),
            "classification_auditability_ready": dispatch.get(
                "classification_auditability_ready"
            ),
        },
        "block_c_classification": {
            "legacy_bucket_mapping_rate_pct": classification.get(
                "legacy_bucket_mapping_rate_pct"
            ),
            "unclassified_pending_taxonomy_count": classification.get(
                "unclassified_pending_taxonomy_count"
            ),
            "new_bucket_candidate_count": classification.get("new_bucket_candidate_count"),
            "bucket_case_count_table": classification.get("bucket_case_count_table"),
        },
        "block_d_admission": {
            "representative_authority_admission": admission,
            "primary_substrate_gap": gap,
            "can_enter_broader_authority_profile": can_enter,
        },
        "upstream_v057": {
            "version_decision": v057["conclusion"]["version_decision"],
            "phase_status": v057["conclusion"]["phase_status"],
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", result)

    bucket_table_lines = []
    for bucket, count in (classification.get("bucket_case_count_table") or {}).items():
        bucket_table_lines.append(f"- `{bucket}`: {count}")

    md = textwrap.dedent(f"""
        # v0.6.0 Closeout

        **Status**: {overall_status}
        **version_decision**: `{version_decision}`
        **representative_authority_admission**: `{admission}`
        **primary_substrate_gap**: `{gap}`
        **can_enter_broader_authority_profile**: {can_enter}
        **v0_6_1_handoff_mode**: `{handoff_mode}`
        **do_not_revert_to_v0_5_boundary_pressure_by_default**: true

        ## Block A — Substrate
        - cases: {substrate.get('case_count')}
        - complexity: {substrate.get('complexity_breakdown')}
        - slice class: {substrate.get('slice_class_breakdown')}
        - already covered: {substrate.get('already_covered_pct')}%

        ## Block B — Dispatch Cleanliness
        - level: {dispatch.get('dispatch_cleanliness_level')}
        - ambiguity: {dispatch.get('attribution_ambiguity_rate_pct')}%
        - auditability ready: {dispatch.get('classification_auditability_ready')}

        ## Block C — Legacy Bucket Classification
        - legacy mapping rate: {classification.get('legacy_bucket_mapping_rate_pct')}%
        - unclassified pending: {classification.get('unclassified_pending_taxonomy_count')}
        - new bucket candidates: {classification.get('new_bucket_candidate_count')}

        ### Bucket table
        {chr(10).join(bucket_table_lines)}

        ## Block D — Authority Admission
        - admission: {admission}
        - gap: {gap}
        - can enter: {can_enter}
    """).strip()
    write_text(out_dir / "summary.md", md)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Block E: v0.6.0 version closeout")
    parser.add_argument("--v057-closeout", type=Path, default=DEFAULT_V057_CLOSEOUT_PATH)
    parser.add_argument(
        "--substrate-dir", type=Path, default=DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR
    )
    parser.add_argument(
        "--dispatch-dir", type=Path, default=DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR
    )
    parser.add_argument(
        "--classification-dir",
        type=Path,
        default=DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR,
    )
    parser.add_argument(
        "--admission-dir", type=Path, default=DEFAULT_AUTHORITY_ADMISSION_OUT_DIR
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_CLOSEOUT_OUT_DIR)
    args = parser.parse_args()

    result = build_closeout(
        v057_closeout_path=args.v057_closeout,
        substrate_dir=args.substrate_dir,
        dispatch_dir=args.dispatch_dir,
        classification_dir=args.classification_dir,
        admission_dir=args.admission_dir,
        out_dir=args.out_dir,
    )
    print(
        f"[Block E] status={result['status']}  "
        f"version_decision={result['conclusion']['version_decision']}  "
        f"handoff={result['conclusion']['v0_6_1_handoff_mode']}"
    )


if __name__ == "__main__":
    main()
