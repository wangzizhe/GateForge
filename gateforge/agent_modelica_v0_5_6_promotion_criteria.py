from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_6_common import (
    BRANCH_PATCH_TYPES,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
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


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_promotion_criteria"


def build_v056_promotion_criteria(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROMOTION_CRITERIA_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v056_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)

    minimum_required_evidence_table = {
        "entry_ready": True,
        "first_fix_ready": True,
        "discovery_ready": True,
        "widened_ready": True,
        "boundedness_chain_intact": True,
        "minimum_widened_task_count": 6,
    }
    structural_independence_negative_rule = (
        "If all branch repair behaviors are fully absorbed by the parent family patch contract, "
        "the branch may not be promoted as new_family_supported."
    )
    promotion_level_candidates = [
        "stable_branch_only",
        "family_extension_supported",
        "new_family_supported",
    ]
    promotion_criteria_frozen = bool(integrity.get("promotion_admission_ready"))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if promotion_criteria_frozen else "FAIL",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "promotion_criteria_frozen": promotion_criteria_frozen,
        "promotion_level_candidates": promotion_level_candidates,
        "minimum_required_evidence_table": minimum_required_evidence_table,
        "parent_family_id": PARENT_FAMILY_ID,
        "parent_patch_contract_types": sorted(PARENT_PATCH_TYPES),
        "branch_patch_contract_types": sorted(BRANCH_PATCH_TYPES),
        "structural_independence_negative_rule": structural_independence_negative_rule,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.6 Promotion Criteria",
                "",
                f"- promotion_criteria_frozen: `{payload.get('promotion_criteria_frozen')}`",
                f"- promotion_level_candidates: `{', '.join(promotion_level_candidates)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.6 promotion criteria summary.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROMOTION_CRITERIA_OUT_DIR))
    args = parser.parse_args()
    payload = build_v056_promotion_criteria(
        handoff_integrity_path=str(args.handoff_integrity),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "promotion_criteria_frozen": payload.get("promotion_criteria_frozen")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
