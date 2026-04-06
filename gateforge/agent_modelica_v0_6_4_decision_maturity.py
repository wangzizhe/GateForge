from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_4_candidate_pressure import build_v064_candidate_pressure
from .agent_modelica_v0_6_4_common import (
    DEFAULT_CANDIDATE_PRESSURE_OUT_DIR,
    DEFAULT_DECISION_MATURITY_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PROFILE_REFINEMENT_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_4_profile_refinement import build_v064_profile_refinement


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_decision_maturity"


def build_v064_decision_maturity(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    profile_refinement_path: str = str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR / "summary.json"),
    candidate_pressure_path: str = str(DEFAULT_CANDIDATE_PRESSURE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DECISION_MATURITY_OUT_DIR),
) -> dict:
    if not Path(profile_refinement_path).exists():
        build_v064_profile_refinement(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(profile_refinement_path).parent),
        )
    if not Path(candidate_pressure_path).exists():
        build_v064_candidate_pressure(
            profile_refinement_path=profile_refinement_path,
            out_dir=str(Path(candidate_pressure_path).parent),
        )

    integrity = load_json(handoff_integrity_path) if Path(handoff_integrity_path).exists() else {"status": "FAIL"}
    refinement = load_json(profile_refinement_path)
    candidate = load_json(candidate_pressure_path)

    if integrity.get("status") != "PASS":
        decision_input_maturity = "invalid"
        maturity_gap = "upstream_chain_integrity_invalid"
        why_not_ready_yet = "The upstream representative chain is no longer trustworthy."
        informative = False
    elif refinement.get("representative_logic_delta") == "unbounded_change" or not refinement.get("legacy_taxonomy_still_sufficient", False):
        decision_input_maturity = "invalid"
        maturity_gap = "representative_logic_or_taxonomy_invalid"
        why_not_ready_yet = "The representative-distribution logic or legacy taxonomy is no longer stable enough for late v0.6 decision work."
        informative = False
    elif candidate.get("open_world_candidate_supported") or candidate.get("targeted_expansion_candidate_supported"):
        decision_input_maturity = "ready"
        maturity_gap = "none"
        why_not_ready_yet = ""
        informative = True
    elif (
        candidate.get("near_miss_open_world_candidate")
        or candidate.get("near_miss_targeted_expansion_candidate")
        or str(candidate.get("dominant_fragility_source") or "none") != "none"
    ):
        decision_input_maturity = "partial"
        maturity_gap = "candidate_threshold_near_miss_or_fragility_source"
        why_not_ready_yet = (
            "The late-phase decision basis is still below the formal candidate threshold, "
            "but the remaining gap is now localized and more informative than in v0.6.3."
        )
        informative = True
    else:
        decision_input_maturity = "invalid"
        maturity_gap = "candidate_pressure_not_auditable"
        why_not_ready_yet = "The candidate-pressure picture is not strong enough to justify even a partial late-phase basis."
        informative = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if decision_input_maturity in {"ready", "partial"} else "FAIL",
        "decision_input_maturity": decision_input_maturity,
        "maturity_gap": maturity_gap,
        "why_not_ready_yet": why_not_ready_yet,
        "is_partial_more_informative_than_v0_6_3": informative if decision_input_maturity == "partial" else False,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.4 Decision Maturity",
                "",
                f"- decision_input_maturity: `{decision_input_maturity}`",
                f"- maturity_gap: `{maturity_gap}`",
                f"- is_partial_more_informative_than_v0_6_3: `{payload['is_partial_more_informative_than_v0_6_3']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.4 decision-maturity adjudication.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-refinement", default=str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR / "summary.json"))
    parser.add_argument("--candidate-pressure", default=str(DEFAULT_CANDIDATE_PRESSURE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DECISION_MATURITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v064_decision_maturity(
        handoff_integrity_path=str(args.handoff_integrity),
        profile_refinement_path=str(args.profile_refinement),
        candidate_pressure_path=str(args.candidate_pressure),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision_input_maturity": payload.get("decision_input_maturity")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
