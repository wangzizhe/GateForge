"""Block D: Representative Authority Admission for v0.6.0.

Determines whether the representative substrate can serve as the
canonical starting point for the v0.6.x broader authority profile
mainline.

Routing rules (from PLAN_V0_6_0):
  dispatch_cleanliness_level == "failed"
    → representative_authority_admission = invalid   (no partial allowed)

  dispatch OK + mapping_rate >= 60%
    → representative_authority_admission = ready

  dispatch OK + mapping_rate < 60%
    → representative_authority_admission = partial

  representativeness claim itself not auditable
    → representative_authority_admission = invalid
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any

from .agent_modelica_v0_6_0_common import (
    DEFAULT_AUTHORITY_ADMISSION_OUT_DIR,
    DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
    DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR,
    DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    LEGACY_BUCKET_MAPPING_RATE_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _compute_admission(
    substrate: dict[str, Any],
    dispatch: dict[str, Any],
    classification: dict[str, Any],
) -> tuple[str, str, bool]:
    """Return (admission_status, primary_substrate_gap, can_enter_broader_authority_profile)."""

    representativeness_ok = (
        substrate.get("representative_slice_frozen", False)
        and substrate.get("sampling_strategy_not_boundary_pressure_driven", False)
        and bool(substrate.get("representativeness_criterion"))
        and bool(substrate.get("why_more_representative_than_v0_5"))
    )

    cleanliness_level = dispatch.get("dispatch_cleanliness_level", "failed")
    auditability_ok = dispatch.get("classification_auditability_ready", False)

    mapping_rate = classification.get("legacy_bucket_mapping_rate_pct", 0.0)
    mapping_ok = mapping_rate >= LEGACY_BUCKET_MAPPING_RATE_MIN

    # Hard rule: failed dispatch → invalid (cannot be partial)
    if cleanliness_level == "failed" or not auditability_ok:
        return (
            "invalid",
            "dispatch_cleanliness_failed",
            False,
        )

    if not representativeness_ok:
        return (
            "invalid",
            "representativeness_claim_not_auditable",
            False,
        )

    if mapping_ok:
        return (
            "ready",
            "none",
            True,
        )

    # dispatch OK + representativeness OK but mapping rate too low
    gap = (
        f"legacy_bucket_mapping_rate_pct={mapping_rate:.1f}% "
        f"below_threshold={LEGACY_BUCKET_MAPPING_RATE_MIN}%"
    )
    return (
        "partial",
        gap,
        False,
    )


def build_authority_admission(
    substrate_dir: Path = DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    dispatch_dir: Path = DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
    classification_dir: Path = DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR,
    out_dir: Path = DEFAULT_AUTHORITY_ADMISSION_OUT_DIR,
) -> dict[str, Any]:
    substrate = load_json(substrate_dir / "summary.json")
    dispatch = load_json(dispatch_dir / "summary.json")
    classification = load_json(classification_dir / "summary.json")

    admission, primary_substrate_gap, can_enter = _compute_admission(
        substrate, dispatch, classification
    )

    result: dict[str, Any] = {
        "schema_version": f"{SCHEMA_PREFIX}_authority_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admission in {"ready", "partial"} else "FAIL",
        "representative_authority_admission": admission,
        "primary_substrate_gap": primary_substrate_gap,
        "can_enter_broader_authority_profile": can_enter,
        "evidence_summary": {
            "representative_slice_frozen": substrate.get("representative_slice_frozen"),
            "sampling_strategy_not_boundary_pressure_driven": substrate.get(
                "sampling_strategy_not_boundary_pressure_driven"
            ),
            "dispatch_cleanliness_level": dispatch.get("dispatch_cleanliness_level"),
            "attribution_ambiguity_rate_pct": dispatch.get("attribution_ambiguity_rate_pct"),
            "policy_baseline_valid": dispatch.get("policy_baseline_valid"),
            "classification_auditability_ready": dispatch.get(
                "classification_auditability_ready"
            ),
            "legacy_bucket_mapping_rate_pct": classification.get(
                "legacy_bucket_mapping_rate_pct"
            ),
            "unclassified_pending_taxonomy_count": classification.get(
                "unclassified_pending_taxonomy_count"
            ),
        },
        "routing_rule_applied": (
            "dispatch_ok + representativeness_ok + mapping_rate>=60 → ready"
            if admission == "ready"
            else (
                "dispatch_failed → invalid"
                if primary_substrate_gap == "dispatch_cleanliness_failed"
                else (
                    "representativeness_not_auditable → invalid"
                    if primary_substrate_gap == "representativeness_claim_not_auditable"
                    else "dispatch_ok + mapping_rate<60 → partial"
                )
            )
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", result)

    md = textwrap.dedent(f"""
        # Block D: Representative Authority Admission — v0.6.0

        **Status**: {result['status']}
        **Admission**: `{admission}`
        **Primary substrate gap**: `{primary_substrate_gap}`
        **Can enter broader authority profile**: {can_enter}

        ## Evidence summary
        - representative_slice_frozen: {result['evidence_summary']['representative_slice_frozen']}
        - dispatch_cleanliness_level: {result['evidence_summary']['dispatch_cleanliness_level']}
        - attribution_ambiguity_rate_pct: {result['evidence_summary']['attribution_ambiguity_rate_pct']}%
        - legacy_bucket_mapping_rate_pct: {result['evidence_summary']['legacy_bucket_mapping_rate_pct']}%
        - unclassified_pending_taxonomy_count: {result['evidence_summary']['unclassified_pending_taxonomy_count']}

        ## Routing rule applied
        {result['routing_rule_applied']}
    """).strip()
    write_text(out_dir / "summary.md", md)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Block D: v0.6.0 representative authority admission"
    )
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
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_AUTHORITY_ADMISSION_OUT_DIR)
    args = parser.parse_args()

    result = build_authority_admission(
        substrate_dir=args.substrate_dir,
        dispatch_dir=args.dispatch_dir,
        classification_dir=args.classification_dir,
        out_dir=args.out_dir,
    )
    print(
        f"[Block D] status={result['status']}  "
        f"admission={result['representative_authority_admission']}  "
        f"can_enter={result['can_enter_broader_authority_profile']}"
    )


if __name__ == "__main__":
    main()
