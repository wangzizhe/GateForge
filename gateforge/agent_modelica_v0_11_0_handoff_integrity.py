from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_0_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V106_CLOSEOUT_PATH,
    DEFAULT_V108_CLOSEOUT_PATH,
    EXPECTED_V103_SUBSTRATE_SIZE,
    EXPECTED_V103_VERSION_DECISION,
    EXPECTED_V104_PROFILE_RUN_COUNT_MIN,
    EXPECTED_V104_UNCLASSIFIED_NON_SUCCESS_COUNT,
    EXPECTED_V104_VERSION_DECISION,
    EXPECTED_V106_ADJUDICATION_LABEL,
    EXPECTED_V106_DOMINANT_NON_SUCCESS_LABEL_FAMILY,
    EXPECTED_V106_VERSION_DECISION,
    EXPECTED_V108_CAVEAT,
    EXPECTED_V108_NEXT_PRIMARY_QUESTION,
    EXPECTED_V108_PHASE_STATUS,
    EXPECTED_V108_PHASE_STOP_CONDITION_STATUS,
    EXPECTED_V108_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v110_handoff_integrity(
    *,
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    v108_closeout_path: str = str(DEFAULT_V108_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    v103 = load_json(v103_closeout_path).get("conclusion", {})
    v104 = load_json(v104_closeout_path).get("conclusion", {})
    v106 = load_json(v106_closeout_path).get("conclusion", {})
    v108 = load_json(v108_closeout_path).get("conclusion", {})

    checks = {
        "v108_version_decision_ok": v108.get("version_decision") == EXPECTED_V108_VERSION_DECISION,
        "v108_phase_status_ok": v108.get("phase_status") == EXPECTED_V108_PHASE_STATUS,
        "v108_phase_stop_condition_status_ok": v108.get("phase_stop_condition_status")
        == EXPECTED_V108_PHASE_STOP_CONDITION_STATUS,
        "v108_explicit_caveat_ok": bool(v108.get("explicit_caveat_present"))
        and v108.get("explicit_caveat_label") == EXPECTED_V108_CAVEAT,
        "v108_next_primary_question_ok": v108.get("next_primary_phase_question")
        == EXPECTED_V108_NEXT_PRIMARY_QUESTION,
        "v108_do_not_continue_ok": bool(v108.get("do_not_continue_v0_10_same_real_origin_refinement_by_default")),
        "v103_version_decision_ok": v103.get("version_decision") == EXPECTED_V103_VERSION_DECISION,
        "v103_substrate_size_ok": v103.get("real_origin_substrate_size") == EXPECTED_V103_SUBSTRATE_SIZE,
        "v104_version_decision_ok": v104.get("version_decision") == EXPECTED_V104_VERSION_DECISION,
        "v104_profile_run_count_ok": int(v104.get("profile_run_count") or 0) >= EXPECTED_V104_PROFILE_RUN_COUNT_MIN,
        "v104_unclassified_non_success_ok": v104.get("profile_non_success_unclassified_count")
        == EXPECTED_V104_UNCLASSIFIED_NON_SUCCESS_COUNT,
        "v106_version_decision_ok": v106.get("version_decision") == EXPECTED_V106_VERSION_DECISION,
        "v106_adjudication_label_ok": v106.get("final_adjudication_label") == EXPECTED_V106_ADJUDICATION_LABEL,
        "v106_partial_check_ok": bool(v106.get("partial_check_pass")),
        "v106_dominant_non_success_label_family_ok": v106.get("dominant_non_success_label_family")
        == EXPECTED_V106_DOMINANT_NON_SUCCESS_LABEL_FAMILY,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_v103_version_decision": v103.get("version_decision"),
        "upstream_v104_version_decision": v104.get("version_decision"),
        "upstream_v106_version_decision": v106.get("version_decision"),
        "upstream_v108_version_decision": v108.get("version_decision"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.0 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_v108_version_decision: `{payload['upstream_v108_version_decision']}`",
                f"- upstream_v103_version_decision: `{payload['upstream_v103_version_decision']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.0 handoff integrity artifact.")
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--v108-closeout", default=str(DEFAULT_V108_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v110_handoff_integrity(
        v103_closeout_path=str(args.v103_closeout),
        v104_closeout_path=str(args.v104_closeout),
        v106_closeout_path=str(args.v106_closeout),
        v108_closeout_path=str(args.v108_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
