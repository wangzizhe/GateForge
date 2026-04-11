from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V113_CLOSEOUT_PATH,
    MIN_PROFILE_RUN_COUNT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v114_handoff_integrity(
    *,
    v113_closeout_path: str = str(DEFAULT_V113_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v113_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    replay_pack = (
        closeout.get("product_gap_profile_replay_pack")
        if isinstance(closeout.get("product_gap_profile_replay_pack"), dict)
        else {}
    )
    characterization = (
        closeout.get("product_gap_profile_characterization")
        if isinstance(closeout.get("product_gap_profile_characterization"), dict)
        else {}
    )

    checks = {
        "version_decision_matches": conclusion.get("version_decision")
        == "v0_11_3_first_product_gap_profile_characterized",
        "profile_status_ok": conclusion.get("first_product_gap_profile_status") == "characterized",
        "handoff_mode_expected": conclusion.get("v0_11_4_handoff_mode")
        == "freeze_first_product_gap_thresholds",
        "profile_run_count_floor_met": int(replay_pack.get("product_gap_profile_run_count") or 0) >= MIN_PROFILE_RUN_COUNT,
        "runtime_evidence_complete": bool(replay_pack.get("runtime_product_gap_evidence_completeness_pass")),
        "placeholders_replaced": bool(replay_pack.get("observation_placeholder_fully_replaced")),
        "non_success_unclassified_zero": int(characterization.get("product_gap_non_success_unclassified_count") or 0) == 0,
        "candidate_gap_family_interpretable": characterization.get("candidate_dominant_gap_family_interpretability")
        == "interpretable",
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_11_4_handoff_mode"),
        "upstream_profile_characterized": conclusion.get("first_product_gap_profile_status"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.4 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.4 handoff integrity artifact.")
    parser.add_argument("--v113-closeout", default=str(DEFAULT_V113_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v114_handoff_integrity(
        v113_closeout_path=str(args.v113_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
