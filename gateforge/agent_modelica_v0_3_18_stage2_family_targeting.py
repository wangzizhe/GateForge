from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_18_stage2_common import (
    DEFAULT_CHARACTERIZATION_OUT_DIR,
    DEFAULT_TARGETING_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_stage2_family_targeting"


def build_stage2_family_targeting(
    *,
    characterization_path: str = str(DEFAULT_CHARACTERIZATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_TARGETING_OUT_DIR),
) -> dict:
    characterization = load_json(characterization_path)
    mutation_sketches = [
        {
            "target_action_type": "component_api_alignment",
            "family_id_hint": "stage2_component_api_alignment_dual_mismatch",
            "targeting_status": "target",
            "complexity_tier_scope": ["simple", "medium"],
            "source_model_pattern": "MSL-backed models with one or two focal components whose public parameter/class surface is well documented",
            "error_to_inject": "replace a valid component class path or parameter name with a sibling-but-invalid API symbol",
            "expected_first_failure": "stage_2_structural_balance_reference|undefined_symbol",
            "expected_second_residual": "stage_2_structural_balance_reference|undefined_symbol",
            "design_note": "The multiround version should chain two local API mismatches so that fixing the first bad class/parameter reveals a second bad modified element on a nearby component.",
        }
    ]
    excluded_action_types = [
        {
            "action_type": "local_connection_fix",
            "reason": "underconstrained mechanical closure still requires topology intent rather than component-doc lookup",
        },
        {
            "action_type": "medium_redeclare_alignment",
            "reason": "fluid medium redeclare consistency spans multiple components and likely needs stronger loop support before it becomes a synthetic target",
        },
        {
            "action_type": "topology_reconstruction",
            "reason": "complex structural redesign is outside the current local repair loop",
        },
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if characterization else "FAIL",
        "authority_confirmation_status": norm(characterization.get("authority_confirmation_status")) or "PENDING_USER_CONFIRMATION",
        "characterization_path": str(Path(characterization_path).resolve()) if Path(characterization_path).exists() else str(characterization_path),
        "provisional_version_decision": norm(characterization.get("provisional_version_decision")) or "stage_2_partially_repairable",
        "target_repair_action_types": ["component_api_alignment"],
        "excluded_action_types": excluded_action_types,
        "complexity_tier_scope": {
            "target": ["simple", "medium"],
            "exclude_for_now": ["complex"],
        },
        "loop_upgrade_requirements": [
            "inject retrievable component interface documentation into the repair loop",
            "add a structure-aware policy before targeting medium redeclare consistency or topology reconstruction",
        ],
        "mutation_sketches": mutation_sketches,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.18 Stage_2 Family Targeting",
                "",
                f"- status: `{payload.get('status')}`",
                f"- provisional_version_decision: `{payload.get('provisional_version_decision')}`",
                f"- target_repair_action_types: `{', '.join(payload.get('target_repair_action_types') or [])}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.18 stage_2 family-targeting draft.")
    parser.add_argument("--characterization", default=str(DEFAULT_CHARACTERIZATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_TARGETING_OUT_DIR))
    args = parser.parse_args()
    payload = build_stage2_family_targeting(
        characterization_path=str(args.characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "target_repair_action_types": payload.get("target_repair_action_types")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
