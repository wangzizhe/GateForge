from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_ADJUDICATION_OUT_DIR,
    DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_1_handoff_integrity import build_v061_handoff_integrity
from .agent_modelica_v0_6_1_live_run import build_v061_live_run
from .agent_modelica_v0_6_1_profile_adjudication import build_v061_profile_adjudication
from .agent_modelica_v0_6_1_profile_classification import build_v061_profile_classification


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v061_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    profile_classification_path: str = str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"),
    profile_adjudication_path: str = str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v061_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(live_run_path).exists():
        build_v061_live_run(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(live_run_path).parent),
        )
    if not Path(profile_classification_path).exists():
        build_v061_profile_classification(
            live_run_path=live_run_path,
            out_dir=str(Path(profile_classification_path).parent),
        )
    if not Path(profile_adjudication_path).exists():
        build_v061_profile_adjudication(
            live_run_path=live_run_path,
            profile_classification_path=profile_classification_path,
            out_dir=str(Path(profile_adjudication_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    live_run = load_json(live_run_path)
    classification = load_json(profile_classification_path)
    adjudication = load_json(profile_adjudication_path)

    integrity_ok = integrity.get("status") == "PASS"
    profile_status = str(adjudication.get("profile_status") or "invalid")
    if not integrity_ok:
        version_decision = "v0_6_1_handoff_substrate_invalid"
        handoff_mode = "repair_representative_profile_substrate_first"
        profile_status = "invalid"
    elif profile_status == "invalid":
        version_decision = "v0_6_1_handoff_substrate_invalid"
        handoff_mode = "repair_representative_profile_substrate_first"
    elif profile_status == "partial":
        version_decision = "v0_6_1_authority_profile_partial"
        handoff_mode = "continue_authority_profile_characterization_on_same_slice"
    else:
        version_decision = "v0_6_1_authority_profile_ready"
        handoff_mode = "widen_or_stratify_authority_profile_under_same_distribution_logic"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if profile_status in {"ready", "partial"} else "FAIL",
        "closeout_status": "V0_6_1_AUTHORITY_PROFILE_READY" if profile_status == "ready" else (
            "V0_6_1_AUTHORITY_PROFILE_PARTIAL" if profile_status == "partial" else "V0_6_1_HANDOFF_SUBSTRATE_INVALID"
        ),
        "conclusion": {
            "version_decision": version_decision,
            "profile_status": profile_status,
            "primary_profile_gap": adjudication.get("primary_profile_gap"),
            "stable_coverage_share_pct": adjudication.get("stable_coverage_share_pct"),
            "fragile_coverage_share_pct": adjudication.get("fragile_coverage_share_pct"),
            "limited_or_uncovered_share_pct": adjudication.get("limited_or_uncovered_share_pct"),
            "v0_6_2_handoff_mode": handoff_mode,
            "do_not_reopen_v0_5_style_boundary_pressure_by_default": True,
        },
        "handoff_integrity": integrity,
        "live_run": {
            "live_run_case_count": live_run.get("live_run_case_count"),
            "dispatch_cleanliness_level_after_live_run": live_run.get("dispatch_cleanliness_level_after_live_run"),
            "signature_advance_case_count": live_run.get("signature_advance_case_count"),
        },
        "profile_classification": {
            "covered_success_count": classification.get("covered_success_count"),
            "covered_but_fragile_count": classification.get("covered_but_fragile_count"),
            "dispatch_or_policy_limited_count": classification.get("dispatch_or_policy_limited_count"),
            "bounded_uncovered_subtype_candidate_count": classification.get("bounded_uncovered_subtype_candidate_count"),
            "topology_or_open_world_spillover_count": classification.get("topology_or_open_world_spillover_count"),
            "legacy_bucket_mapping_rate_pct": classification.get("legacy_bucket_mapping_rate_pct"),
        },
        "profile_adjudication": adjudication,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- profile_status: `{profile_status}`",
                f"- stable_coverage_share_pct: `{adjudication.get('stable_coverage_share_pct')}`",
                f"- fragile_coverage_share_pct: `{adjudication.get('fragile_coverage_share_pct')}`",
                f"- limited_or_uncovered_share_pct: `{adjudication.get('limited_or_uncovered_share_pct')}`",
                f"- v0_6_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.1 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-classification", default=str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-adjudication", default=str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v061_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        live_run_path=str(args.live_run),
        profile_classification_path=str(args.profile_classification),
        profile_adjudication_path=str(args.profile_adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
