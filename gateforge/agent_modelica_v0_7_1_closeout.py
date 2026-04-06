from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_1_common import (
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
from .agent_modelica_v0_7_1_handoff_integrity import build_v071_handoff_integrity
from .agent_modelica_v0_7_1_live_run import build_v071_live_run
from .agent_modelica_v0_7_1_profile_adjudication import build_v071_profile_adjudication
from .agent_modelica_v0_7_1_profile_classification import build_v071_profile_classification


def build_v071_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    profile_classification_path: str = str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"),
    profile_adjudication_path: str = str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v071_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_1_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_1_handoff_substrate_invalid",
                "profile_admission_status": "invalid",
                "stable_coverage_share_pct": None,
                "fragile_but_usable_share_pct": None,
                "spillover_share_pct_after_live_run": None,
                "legacy_bucket_mapping_rate_pct_after_live_run": None,
                "dominant_pressure_source": None,
                "v0_7_2_handoff_mode": "repair_open_world_adjacent_substrate_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.7.1 Closeout\n")
        return payload

    if not Path(live_run_path).exists():
        build_v071_live_run(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(live_run_path).parent),
        )
    if not Path(profile_classification_path).exists():
        build_v071_profile_classification(
            live_run_path=live_run_path,
            out_dir=str(Path(profile_classification_path).parent),
        )
    if not Path(profile_adjudication_path).exists():
        build_v071_profile_adjudication(
            profile_classification_path=profile_classification_path,
            out_dir=str(Path(profile_adjudication_path).parent),
        )

    live_run = load_json(live_run_path)
    classification = load_json(profile_classification_path)
    adjudication = load_json(profile_adjudication_path)
    status = str(adjudication.get("profile_admission_status") or "invalid")
    if status == "ready":
        version_decision = "v0_7_1_readiness_profile_ready"
        handoff = "widen_or_stratify_readiness_profile_under_same_open_world_adjacent_logic"
    elif status == "partial":
        version_decision = "v0_7_1_readiness_profile_partial"
        handoff = "stabilize_readiness_profile_under_same_substrate"
    else:
        version_decision = "v0_7_1_handoff_substrate_invalid"
        handoff = "repair_open_world_adjacent_substrate_first"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"ready", "partial"} else "FAIL",
        "closeout_status": {
            "ready": "V0_7_1_READINESS_PROFILE_READY",
            "partial": "V0_7_1_READINESS_PROFILE_PARTIAL",
            "invalid": "V0_7_1_HANDOFF_SUBSTRATE_INVALID",
        }[status],
        "conclusion": {
            "version_decision": version_decision,
            "profile_admission_status": status,
            "stable_coverage_share_pct": adjudication.get("stable_coverage_share_pct"),
            "fragile_but_usable_share_pct": adjudication.get("fragile_but_usable_share_pct"),
            "spillover_share_pct_after_live_run": adjudication.get("spillover_share_pct_after_live_run"),
            "legacy_bucket_mapping_rate_pct_after_live_run": adjudication.get("legacy_bucket_mapping_rate_pct_after_live_run"),
            "dominant_pressure_source": adjudication.get("dominant_pressure_source"),
            "v0_7_2_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "live_run": {
            "live_run_case_count": live_run.get("live_run_case_count"),
            "signature_advance_case_count": live_run.get("signature_advance_case_count"),
        },
        "profile_classification": classification,
        "profile_adjudication": adjudication,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- profile_admission_status: `{status}`",
                f"- stable_coverage_share_pct: `{adjudication.get('stable_coverage_share_pct')}`",
                f"- fragile_but_usable_share_pct: `{adjudication.get('fragile_but_usable_share_pct')}`",
                f"- spillover_share_pct_after_live_run: `{adjudication.get('spillover_share_pct_after_live_run')}`",
                f"- v0_7_2_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.1 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-classification", default=str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-adjudication", default=str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v071_closeout(
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
