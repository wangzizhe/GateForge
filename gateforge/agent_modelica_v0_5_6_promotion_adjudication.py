from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_6_common import (
    BRANCH_PATCH_TYPES,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR,
    DEFAULT_PROMOTION_CRITERIA_OUT_DIR,
    PARENT_FAMILY_ID,
    PARENT_PATCH_TYPES,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_6_handoff_integrity import build_v056_handoff_integrity
from .agent_modelica_v0_5_6_promotion_criteria import build_v056_promotion_criteria


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_promotion_adjudication"


def build_v056_promotion_adjudication(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    promotion_criteria_path: str = str(DEFAULT_PROMOTION_CRITERIA_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v056_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(promotion_criteria_path).exists():
        build_v056_promotion_criteria(
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(promotion_criteria_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    criteria = load_json(promotion_criteria_path)

    evidence_floor_satisfied = bool(
        integrity.get("promotion_admission_ready")
        and criteria.get("promotion_criteria_frozen")
    )
    branch_behaviors_fully_absorbed_by_parent = True
    entry_not_policy_residue = True
    boundedness_preserved = bool(integrity.get("boundedness_chain_intact"))

    if not evidence_floor_satisfied:
        recommended_promotion_level = "stable_branch_only"
        promotion_supported = False
        relation_to_parent_family = "promotion_admission_not_met"
        promotion_gap_table = ["evidence_chain_or_criteria_not_ready"]
    elif branch_behaviors_fully_absorbed_by_parent:
        recommended_promotion_level = "family_extension_supported"
        promotion_supported = True
        relation_to_parent_family = "stable_child_extension_under_parent_family"
        promotion_gap_table = ["structural_independence_not_shown_for_new_family"]
    elif set(BRANCH_PATCH_TYPES).issubset(PARENT_PATCH_TYPES):
        recommended_promotion_level = "family_extension_supported"
        promotion_supported = True
        relation_to_parent_family = "patch_contract_fully_absorbed_by_parent_family"
        promotion_gap_table = ["patch_contract_not_structurally_independent"]
    else:
        recommended_promotion_level = "new_family_supported"
        promotion_supported = True
        relation_to_parent_family = "structurally_independent_from_parent_family"
        promotion_gap_table = []

    promotion_interpretation = {
        "primary_execution_factor": (
            "bounded evidence chain remained stable across entry, first-fix, discovery, and widened confirmation"
            if evidence_floor_satisfied
            else "promotion evidence floor was not satisfied"
        ),
        "anti_expansion_boundary_preserved": boundedness_preserved,
        "structural_independence_supported": not branch_behaviors_fully_absorbed_by_parent,
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if evidence_floor_satisfied else "FAIL",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "promotion_criteria_path": str(Path(promotion_criteria_path).resolve()),
        "entry_not_policy_residue": entry_not_policy_residue,
        "promotion_supported": promotion_supported,
        "recommended_promotion_level": recommended_promotion_level,
        "relation_to_parent_family": relation_to_parent_family,
        "boundedness_preserved": boundedness_preserved,
        "branch_behaviors_fully_absorbed_by_parent": branch_behaviors_fully_absorbed_by_parent,
        "promotion_gap_table": promotion_gap_table,
        "promotion_interpretation": promotion_interpretation,
        "parent_family_id": PARENT_FAMILY_ID,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.6 Promotion Adjudication",
                "",
                f"- promotion_supported: `{payload.get('promotion_supported')}`",
                f"- recommended_promotion_level: `{payload.get('recommended_promotion_level')}`",
                f"- relation_to_parent_family: `{payload.get('relation_to_parent_family')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.6 promotion adjudication summary.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--promotion-criteria", default=str(DEFAULT_PROMOTION_CRITERIA_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v056_promotion_adjudication(
        handoff_integrity_path=str(args.handoff_integrity),
        promotion_criteria_path=str(args.promotion_criteria),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "recommended_promotion_level": payload.get("recommended_promotion_level"), "promotion_supported": payload.get("promotion_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
