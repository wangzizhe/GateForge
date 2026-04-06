from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_6_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR,
    DEFAULT_PROMOTION_CRITERIA_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_6_handoff_integrity import build_v056_handoff_integrity
from .agent_modelica_v0_5_6_promotion_adjudication import build_v056_promotion_adjudication
from .agent_modelica_v0_5_6_promotion_criteria import build_v056_promotion_criteria


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v056_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    promotion_criteria_path: str = str(DEFAULT_PROMOTION_CRITERIA_OUT_DIR / "summary.json"),
    promotion_adjudication_path: str = str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v056_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(promotion_criteria_path).exists():
        build_v056_promotion_criteria(
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(promotion_criteria_path).parent),
        )
    if not Path(promotion_adjudication_path).exists():
        build_v056_promotion_adjudication(
            handoff_integrity_path=str(handoff_integrity_path),
            promotion_criteria_path=str(promotion_criteria_path),
            out_dir=str(Path(promotion_adjudication_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    criteria = load_json(promotion_criteria_path)
    adjudication = load_json(promotion_adjudication_path)

    if not bool(integrity.get("evidence_chain_integrity_ok")):
        version_decision = "v0_5_6_handoff_substrate_invalid"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"
    elif not bool(adjudication.get("promotion_supported")):
        version_decision = "v0_5_6_promotion_not_supported"
        handoff_mode = "keep_branch_but_do_not_promote_further"
    elif str(adjudication.get("recommended_promotion_level") or "") == "stable_branch_only":
        version_decision = "v0_5_6_branch_level_only"
        handoff_mode = "keep_branch_but_do_not_promote_further"
    else:
        version_decision = "v0_5_6_family_level_promotion_supported"
        handoff_mode = "run_phase_synthesis_with_promoted_branch"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_6_PROMOTION_DECISION_READY",
        "conclusion": {
            "version_decision": version_decision,
            "promotion_supported": adjudication.get("promotion_supported"),
            "recommended_promotion_level": adjudication.get("recommended_promotion_level"),
            "relation_to_parent_family": adjudication.get("relation_to_parent_family"),
            "v0_5_7_handoff_mode": handoff_mode,
            "v0_5_7_primary_eval_question": "Given the branch promotion adjudication, should the next version synthesize the phase around the promoted branch-family relation or keep it as a bounded branch without higher authority claims?",
        },
        "handoff_integrity": integrity,
        "promotion_criteria": criteria,
        "promotion_adjudication": adjudication,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.6 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- recommended_promotion_level: `{(payload.get('conclusion') or {}).get('recommended_promotion_level')}`",
                f"- v0_5_7_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.6 promotion decision closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--promotion-criteria", default=str(DEFAULT_PROMOTION_CRITERIA_OUT_DIR / "summary.json"))
    parser.add_argument("--promotion-adjudication", default=str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v056_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        promotion_criteria_path=str(args.promotion_criteria),
        promotion_adjudication_path=str(args.promotion_adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
