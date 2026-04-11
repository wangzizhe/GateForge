from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_3_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR,
    DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH,
    MAX_UNEXPLAINED_CASE_FLIPS,
    PROFILE_RUN_COUNT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_3_handoff_integrity import build_v113_handoff_integrity
from .agent_modelica_v0_11_3_product_gap_profile_characterization import build_v113_product_gap_profile_characterization
from .agent_modelica_v0_11_3_product_gap_profile_replay_pack import build_v113_product_gap_profile_replay_pack


def build_v113_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    replay_pack_path: str = str(DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    characterization_path: str = str(DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v112_product_gap_substrate_builder_path: str = str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
    profile_run_count: int = PROFILE_RUN_COUNT,
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    replay_path_obj = Path(replay_pack_path)
    characterization_path_obj = Path(characterization_path)

    if not handoff_path_obj.exists():
        build_v113_handoff_integrity(
            v112_closeout_path=v112_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_11_3_PRODUCT_GAP_PROFILE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_11_3_product_gap_profile_inputs_invalid",
                "first_product_gap_profile_status": "invalid",
                "why_this_is_or_is_not_characterized": "The upstream v0.11.2 product-gap substrate handoff is no longer valid, so the first product-gap profile cannot be trusted.",
                "v0_11_4_handoff_mode": "rebuild_v0_11_3_profile_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.11.3 Closeout\n\n- version_decision: `v0_11_3_product_gap_profile_inputs_invalid`\n")
        return payload

    if not replay_path_obj.exists():
        build_v113_product_gap_profile_replay_pack(
            v112_product_gap_substrate_builder_path=v112_product_gap_substrate_builder_path,
            out_dir=str(replay_path_obj.parent),
            profile_run_count=profile_run_count,
        )
    replay_pack = load_json(replay_pack_path)

    if not characterization_path_obj.exists():
        build_v113_product_gap_profile_characterization(
            replay_pack_path=replay_pack_path,
            v112_product_gap_substrate_builder_path=v112_product_gap_substrate_builder_path,
            out_dir=str(characterization_path_obj.parent),
        )
    characterization = load_json(characterization_path)

    runtime_evidence_complete = bool(replay_pack.get("runtime_product_gap_evidence_completeness_pass"))
    candidate_interpretability = str(characterization.get("candidate_dominant_gap_family_interpretability") or "not_interpretable")
    candidate_family = str(characterization.get("candidate_dominant_gap_family") or "mixed_or_not_yet_resolved")
    run_count = int(replay_pack.get("product_gap_profile_run_count") or 0)
    unexplained_flips = int(replay_pack.get("unexplained_case_flip_count") or 0)
    unclassified_count = int(characterization.get("product_gap_non_success_unclassified_count") or 0)

    if (
        runtime_evidence_complete
        and run_count >= PROFILE_RUN_COUNT
        and unexplained_flips <= MAX_UNEXPLAINED_CASE_FLIPS
        and unclassified_count == 0
        and candidate_interpretability == "interpretable"
        and candidate_family != "mixed_or_not_yet_resolved"
    ):
        version_decision = "v0_11_3_first_product_gap_profile_characterized"
        profile_status = "characterized"
        handoff_mode = "freeze_first_product_gap_thresholds"
        status = "PASS"
        why = "The first product-gap profile now carries complete runtime evidence, passes the characterization repeatability floor, and yields an interpretable candidate dominant gap family."
    elif (
        runtime_evidence_complete
        and candidate_interpretability != "not_interpretable"
        and (
            unexplained_flips > MAX_UNEXPLAINED_CASE_FLIPS
            or unclassified_count > 0
            or candidate_family == "mixed_or_not_yet_resolved"
            or candidate_interpretability == "partial"
        )
    ):
        version_decision = "v0_11_3_first_product_gap_profile_partial"
        profile_status = "partial"
        handoff_mode = "finish_product_gap_profile_characterization_first"
        status = "PASS"
        why = "The first product-gap profile is already valid enough to inspect, but the repeatability or dominant-gap interpretability floor remains below the preferred characterization standard."
    else:
        version_decision = "v0_11_3_product_gap_profile_inputs_invalid"
        profile_status = "invalid"
        handoff_mode = "rebuild_v0_11_3_profile_inputs_first"
        status = "FAIL"
        why = "The first product-gap profile is missing required runtime evidence or remains too unstable or opaque to characterize."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "first_product_gap_profile_status": profile_status,
            "why_this_is_or_is_not_characterized": why,
            "v0_11_4_handoff_mode": handoff_mode,
            "workflow_resolution_rate_pct": characterization.get("workflow_resolution_rate_pct"),
            "goal_alignment_rate_pct": characterization.get("goal_alignment_rate_pct"),
            "surface_fix_only_rate_pct": characterization.get("surface_fix_only_rate_pct"),
            "unresolved_rate_pct": characterization.get("unresolved_rate_pct"),
            "candidate_dominant_gap_family": candidate_family,
            "candidate_dominant_gap_family_interpretability": candidate_interpretability,
        },
        "handoff_integrity": handoff,
        "product_gap_profile_replay_pack": replay_pack,
        "product_gap_profile_characterization": characterization,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.3 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- first_product_gap_profile_status: `{profile_status}`",
                f"- candidate_dominant_gap_family: `{candidate_family}`",
                f"- v0_11_4_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.3 closeout artifact.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--replay-pack", default=str(DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--characterization-path", default=str(DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v112-product-gap-substrate-builder", default=str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    parser.add_argument("--profile-run-count", type=int, default=PROFILE_RUN_COUNT)
    args = parser.parse_args()
    payload = build_v113_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        replay_pack_path=str(args.replay_pack),
        characterization_path=str(args.characterization_path),
        v112_closeout_path=str(args.v112_closeout),
        v112_product_gap_substrate_builder_path=str(args.v112_product_gap_substrate_builder),
        out_dir=str(args.out_dir),
        profile_run_count=int(args.profile_run_count),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
